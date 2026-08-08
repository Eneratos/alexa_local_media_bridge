'use strict';

const Alexa = require('ask-sdk-core');
const https = require('https');
const SKILL_VERSION = require('./package.json').version;
const SKILL_USER_AGENT = `AlexaMediaSkill/${SKILL_VERSION}`;

const BRIDGE_BASE_URL = String(
    process.env.BRIDGE_BASE_URL || ''
).trim().replace(/\/+$/, '');

if (!BRIDGE_BASE_URL) {
    throw new Error('BRIDGE_BASE_URL is not configured.');
}

const RESOLVE_API_URL =
    `${BRIDGE_BASE_URL}/api/navidrome/resolve`;

const CURRENT_API_URL =
    `${BRIDGE_BASE_URL}/api/navidrome/current`;

const NEXT_API_URL =
    `${BRIDGE_BASE_URL}/api/navidrome/next`;

const PREVIOUS_API_URL =
    `${BRIDGE_BASE_URL}/api/navidrome/previous`;

const SCROBBLE_API_URL =
    `${BRIDGE_BASE_URL}/api/navidrome/scrobble`;

const AUDIOBOOK_RESOLVE_API_URL =
    `${BRIDGE_BASE_URL}/api/audiobookshelf/resolve`;

const AUDIOBOOK_PROGRESS_API_URL =
    `${BRIDGE_BASE_URL}/api/audiobookshelf/progress`;

const AUDIOBOOK_RESTART_API_URL =
    `${BRIDGE_BASE_URL}/api/audiobookshelf/restart`;

const AUDIOBOOK_CHAPTER_API_URL =
    `${BRIDGE_BASE_URL}/api/audiobookshelf/chapter`;

const AUDIOBOOK_SEEK_API_URL =
    `${BRIDGE_BASE_URL}/api/audiobookshelf/seek`;

const AUDIOBOOK_SERIES_NEIGHBOR_API_URL =
    `${BRIDGE_BASE_URL}/api/audiobookshelf/series-neighbor`;

const CONTROL_SECRET =
    String(
        process.env.CONTROL_SECRET || ''
    ).trim();

if (!CONTROL_SECRET) {
    throw new Error(
        'CONTROL_SECRET is not configured.'
    );
}


function isAudiobookToken(token) {
    return String(token || '').indexOf(
        'abs1.'
    ) === 0;
}

function isNavidromeToken(token) {
    return String(token || '').indexOf(
        'ndq1.'
    ) === 0;
}

function postJson(urlString, payload) {
    return new Promise(function (resolve, reject) {
        const target = new URL(urlString);
        const body = JSON.stringify(payload);

        const options = {
            hostname: target.hostname,
            port: target.port || 443,
            path: target.pathname + target.search,
            method: 'POST',
            headers: {
                'Authorization':
                    'Bearer ' + CONTROL_SECRET,
                'Content-Type':
                    'application/json',
                'Accept':
                    'application/json',
                'Content-Length':
                    Buffer.byteLength(body),
                'User-Agent':
                    SKILL_USER_AGENT
            }
        };

        const request = https.request(
            options,
            function (response) {
                let responseBody = '';

                response.setEncoding('utf8');

                response.on(
                    'data',
                    function (chunk) {
                        responseBody += chunk;

                        if (
                            responseBody.length
                            > 65536
                        ) {
                            request.destroy(
                                new Error(
                                    'Bridge response is too large.'
                                )
                            );
                        }
                    }
                );

                response.on(
                    'end',
                    function () {
                        let parsed;

                        try {
                            parsed = JSON.parse(
                                responseBody
                            );
                        } catch (error) {
                            reject(
                                new Error(
                                    'Bridge returned invalid JSON.'
                                )
                            );
                            return;
                        }

                        if (
                            response.statusCode < 200
                            || response.statusCode >= 300
                        ) {
                            const bridgeError =
                                parsed.error
                                || (
                                    'HTTP '
                                    + response.statusCode
                                );

                            reject(
                                new Error(
                                    'Bridge error: '
                                    + bridgeError
                                )
                            );
                            return;
                        }

                        resolve(parsed);
                    }
                );
            }
        );

        request.setTimeout(
            12000,
            function () {
                request.destroy(
                    new Error(
                        'Bridge request timed out.'
                    )
                );
            }
        );

        request.on(
            'error',
            function (error) {
                reject(error);
            }
        );

        request.write(body);
        request.end();
    });
}


function getSlotValue(handlerInput, slotName) {
    const request =
        handlerInput.requestEnvelope.request || {};

    const intent =
        request.intent || {};

    const slots =
        intent.slots || {};

    const slot =
        slots[slotName];

    if (
        !slot
        || typeof slot.value !== 'string'
    ) {
        return '';
    }

    return slot.value.trim();
}



function getResolvedSlotValue(
    handlerInput,
    slotName
) {
    const request =
        handlerInput.requestEnvelope.request || {};

    const intent =
        request.intent || {};

    const slots =
        intent.slots || {};

    const slot =
        slots[slotName] || {};

    const resolutions =
        slot.resolutions
        && slot.resolutions.resolutionsPerAuthority;

    if (Array.isArray(resolutions)) {
        for (const authority of resolutions) {
            if (
                !authority
                || !authority.status
                || authority.status.code
                    !== 'ER_SUCCESS_MATCH'
                || !Array.isArray(
                    authority.values
                )
            ) {
                continue;
            }

            const first =
                authority.values[0]
                && authority.values[0].value;

            if (
                first
                && typeof first.name === 'string'
                && first.name.trim()
            ) {
                return first.name.trim();
            }
        }
    }

    return getSlotValue(
        handlerInput,
        slotName
    );
}



function canonicalEpisodeNumber(value) {
    const text = String(
        value || ''
    ).trim().replace(',', '.');

    if (!/^\d+(?:\.\d+)?$/.test(text)) {
        return '';
    }

    const number = Number(text);

    if (
        !Number.isFinite(number)
        || number <= 0
    ) {
        return '';
    }

    return String(number);
}


function parseGermanIntegerWords(value) {
    const compact = String(
        value || ''
    )
        .toLowerCase()
        .replace(/[.\u00b7]/g, '')
        .replace(/[\s-]+/g, '');

    if (!compact) {
        return null;
    }

    if (/^\d+$/.test(compact)) {
        return Number(compact);
    }

    const small = {
        null: 0,
        ein: 1,
        eins: 1,
        eine: 1,
        einen: 1,
        zwei: 2,
        drei: 3,
        vier: 4,
        fünf: 5,
        funf: 5,
        sechs: 6,
        sieben: 7,
        acht: 8,
        neun: 9,
        zehn: 10,
        elf: 11,
        zwölf: 12,
        zwolf: 12,
        dreizehn: 13,
        vierzehn: 14,
        fünfzehn: 15,
        funfzehn: 15,
        sechzehn: 16,
        siebzehn: 17,
        achtzehn: 18,
        neunzehn: 19
    };

    if (
        Object.prototype.hasOwnProperty.call(
            small,
            compact
        )
    ) {
        return small[compact];
    }

    const thousandIndex =
        compact.indexOf('tausend');

    if (thousandIndex !== -1) {
        const before =
            compact.slice(0, thousandIndex);

        const after =
            compact.slice(
                thousandIndex + 'tausend'.length
            );

        const multiplier =
            before
                ? parseGermanIntegerWords(before)
                : 1;

        const remainder =
            after
                ? parseGermanIntegerWords(after)
                : 0;

        if (
            multiplier === null
            || remainder === null
        ) {
            return null;
        }

        return multiplier * 1000 + remainder;
    }

    const hundredIndex =
        compact.indexOf('hundert');

    if (hundredIndex !== -1) {
        const before =
            compact.slice(0, hundredIndex);

        const after =
            compact.slice(
                hundredIndex + 'hundert'.length
            );

        const multiplier =
            before
                ? parseGermanIntegerWords(before)
                : 1;

        const remainder =
            after
                ? parseGermanIntegerWords(after)
                : 0;

        if (
            multiplier === null
            || remainder === null
            || multiplier < 1
            || multiplier > 9
        ) {
            return null;
        }

        return multiplier * 100 + remainder;
    }

    const tens = [
        ['zwanzig', 20],
        ['dreißig', 30],
        ['dreissig', 30],
        ['vierzig', 40],
        ['fünfzig', 50],
        ['funfzig', 50],
        ['sechzig', 60],
        ['siebzig', 70],
        ['achtzig', 80],
        ['neunzig', 90]
    ];

    for (const pair of tens) {
        const word = pair[0];
        const number = pair[1];

        if (compact === word) {
            return number;
        }

        const suffix = 'und' + word;

        if (compact.endsWith(suffix)) {
            const unitWord =
                compact.slice(
                    0,
                    compact.length - suffix.length
                );

            const unit =
                parseGermanIntegerWords(unitWord);

            if (
                unit !== null
                && unit >= 1
                && unit <= 9
            ) {
                return number + unit;
            }
        }
    }

    return null;
}


function parseEnglishIntegerWords(value) {
    const text = String(
        value || ''
    )
        .toLowerCase()
        .replace(/-/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();

    if (!text) {
        return null;
    }

    if (/^\d+$/.test(text)) {
        return Number(text);
    }

    const numbers = {
        zero: 0,
        one: 1,
        two: 2,
        three: 3,
        four: 4,
        five: 5,
        six: 6,
        seven: 7,
        eight: 8,
        nine: 9,
        ten: 10,
        eleven: 11,
        twelve: 12,
        thirteen: 13,
        fourteen: 14,
        fifteen: 15,
        sixteen: 16,
        seventeen: 17,
        eighteen: 18,
        nineteen: 19,
        twenty: 20,
        thirty: 30,
        forty: 40,
        fifty: 50,
        sixty: 60,
        seventy: 70,
        eighty: 80,
        ninety: 90
    };

    const words = text
        .split(' ')
        .filter(function (word) {
            return word && word !== 'and';
        });

    let total = 0;
    let current = 0;
    let consumed = false;

    for (const word of words) {
        if (
            Object.prototype.hasOwnProperty.call(
                numbers,
                word
            )
        ) {
            current += numbers[word];
            consumed = true;
            continue;
        }

        if (word === 'hundred') {
            current = (current || 1) * 100;
            consumed = true;
            continue;
        }

        if (word === 'thousand') {
            total += (current || 1) * 1000;
            current = 0;
            consumed = true;
            continue;
        }

        return null;
    }

    return consumed
        ? total + current
        : null;
}


function parseSpokenEpisodeNumber(
    value,
    language
) {
    const direct =
        canonicalEpisodeNumber(value);

    if (direct) {
        return direct;
    }

    const text = String(
        value || ''
    )
        .toLowerCase()
        .replace(/\s+/g, ' ')
        .trim();

    if (!text) {
        return '';
    }

    const decimalSeparators =
        language === 'en'
            ? [' point ']
            : [
                ' komma ',
                ' punkt ',
                /*
                 * The Alexa simulator can interpret
                 * spoken decimal episode numbers such
                 * as "2.1" as "zwei uhr eins".
                 */
                ' uhr '
            ];

    for (const separator of decimalSeparators) {
        const index =
            text.indexOf(separator);

        if (index === -1) {
            continue;
        }

        const left =
            text.slice(0, index).trim();

        const right =
            text.slice(
                index + separator.length
            ).trim();

        const integer =
            language === 'en'
                ? parseEnglishIntegerWords(left)
                : parseGermanIntegerWords(left);

        const fraction =
            language === 'en'
                ? parseEnglishIntegerWords(right)
                : parseGermanIntegerWords(right);

        if (
            integer === null
            || fraction === null
            || integer < 0
            || fraction < 0
        ) {
            return '';
        }

        return canonicalEpisodeNumber(
            String(integer)
            + '.'
            + String(fraction)
        );
    }

    const integer =
        language === 'en'
            ? parseEnglishIntegerWords(text)
            : parseGermanIntegerWords(text);

    if (
        integer === null
        || integer <= 0
    ) {
        return '';
    }

    return String(integer);
}


function parseAudiobookSeriesEpisodeQuery(
    handlerInput,
    value
) {
    let text = String(
        value || ''
    )
        .trim()
        .replace(/\s+/g, ' ')
        .replace(/[.!?]+$/g, '');

    if (!text) {
        return null;
    }

    const language =
        requestLanguage(handlerInput);

    /*
     * SearchQuery should normally contain only the
     * text after "Folge"/"episode". These prefixes
     * are accepted defensively in case Alexa includes
     * one of them in the slot value.
     */
    if (language === 'en') {
        text = text.replace(
            /^(?:episode|book)\s+/i,
            ''
        );
    } else {
        text = text.replace(
            /^(?:folge|hörspielfolge|hörspiel\s+folge)\s+/i,
            ''
        );
    }

    const connector =
        language === 'en'
            ? /^(.+?)\s+(?:of|from)\s+(.+)$/i
            : /^(.+?)\s+(?:von|aus)\s+(.+)$/i;

    const match = connector.exec(text);

    if (match) {
        const episodeNumber =
            parseSpokenEpisodeNumber(
                match[1],
                language
            );

        const query =
            match[2].trim();

        if (
            episodeNumber
            && query
        ) {
            return {
                episodeNumber: episodeNumber,
                query: query
            };
        }
    }

    /*
     * Also accept a request without "von"/"of",
     * e.g. "42 Benjamin Blümchen". The longest
     * valid number prefix wins.
     */
    const words = text.split(' ');

    let result = null;

    for (
        let index = 1;
        index < words.length;
        index += 1
    ) {
        const numberText =
            words.slice(0, index).join(' ');

        const query =
            words.slice(index).join(' ').trim();

        const episodeNumber =
            parseSpokenEpisodeNumber(
                numberText,
                language
            );

        if (
            episodeNumber
            && query
        ) {
            result = {
                episodeNumber: episodeNumber,
                query: query
            };
        }
    }

    return result;
}


function getModeForIntent(intentName) {
    if (intentName === 'PlayAlbumIntent') {
        return 'album';
    }

    if (intentName === 'PlayArtistIntent') {
        return 'artist';
    }

    if (intentName === 'PlayPlaylistIntent') {
        return 'playlist';
    }

    if (intentName === 'PlayRandomIntent') {
        return 'random';
    }

    return 'song';
}


function getAudioPlayerState(handlerInput) {
    const context =
        handlerInput.requestEnvelope.context || {};

    const audioPlayer =
        context.AudioPlayer || {};

    let offset = Number(
        audioPlayer.offsetInMilliseconds || 0
    );

    if (
        !Number.isFinite(offset)
        || offset < 0
    ) {
        offset = 0;
    }

    return {
        token: String(
            audioPlayer.token || ''
        ),
        offsetInMilliseconds:
            Math.floor(offset),
        playerActivity: String(
            audioPlayer.playerActivity || ''
        )
    };
}


function createPlayDirective(
    result,
    playBehavior,
    expectedPreviousToken,
    offsetInMilliseconds
) {
    const stream = {
        token: result.stream.token,
        url: result.stream.url,
        offsetInMilliseconds:
            offsetInMilliseconds || 0
    };

    if (playBehavior === 'ENQUEUE') {
        stream.expectedPreviousToken =
            expectedPreviousToken;
    }

    return {
        type: 'AudioPlayer.Play',
        playBehavior: playBehavior,
        audioItem: {
            stream: stream,
            metadata: {
                title:
                    result.match.title || '',
                subtitle:
                    result.match.artist
                    || result.match.author
                    || ''
            }
        }
    };
}


function createClearAllDirective() {
    return {
        type: 'AudioPlayer.ClearQueue',
        clearBehavior: 'CLEAR_ALL'
    };
}


function resultIsPlayable(result) {
    return Boolean(
        result
        && result.status === 'ok'
        && result.match
        && result.stream
        && result.stream.url
        && result.stream.token
    );
}

async function sendScrobble(
    token,
    eventName
) {
    if (!isNavidromeToken(token)) {
        console.log(
            'No Navidrome token; '
            + 'skipping scrobble.'
        );

        return;
    }

    if (!token) {
        console.error(
            'Scrobble without token:',
            eventName
        );

        return;
    }

    const payload = {
        token: token,
        event: eventName
    };

    if (eventName === 'finished') {
        payload.time = Date.now();
    }

    try {
        const result = await postJson(
            SCROBBLE_API_URL,
            payload
        );

        console.log(
            'Navidrome scrobble:',
            result.event,
            result.match
                ? result.match.artist
                : '',
            result.match
                ? result.match.title
                : ''
        );
    } catch (error) {
        /*
         * A failed scrobble
         * must not interfere with audio playback.
         */
        console.error(
            'Scrobble error:',
            eventName,
            error && error.stack
                ? error.stack
                : String(error)
        );
    }
}


async function sendAudiobookProgress(
    token,
    eventName,
    offsetInMilliseconds
) {
    if (!isAudiobookToken(token)) {
        return;
    }

    let offset = Number(
        offsetInMilliseconds || 0
    );

    if (
        !Number.isFinite(offset)
        || offset < 0
    ) {
        offset = 0;
    }

    offset = Math.floor(offset);

    try {
        const result = await postJson(
            AUDIOBOOK_PROGRESS_API_URL,
            {
                token: token,
                event: eventName,
                offsetInMilliseconds: offset
            }
        );

        const progress =
            result.progress || {};

        const session =
            result.session || {};

        console.log(
            'Audiobookshelf progress:',
            result.event || eventName,
            progress.currentTime !== undefined
                ? progress.currentTime
                : '',
            'seconds',
            session.state || ''
        );
    } catch (error) {
        /*
         * A failed progress sync
         * must not interfere with the AudioPlayer response.
         */
        console.error(
            'Audiobookshelf progress error:',
            eventName,
            error && error.stack
                ? error.stack
                : String(error)
        );
    }
}


function parseIsoDurationSeconds(value) {
    const text = String(
        value || ''
    ).trim().toUpperCase();

    const match = /^P(?:(\d+(?:\.\d+)?)W)?(?:(\d+(?:\.\d+)?)D)?(?:T(?:(\d+(?:\.\d+)?)H)?(?:(\d+(?:\.\d+)?)M)?(?:(\d+(?:\.\d+)?)S)?)?$/.exec(
        text
    );

    if (!match) {
        return null;
    }

    const hasValue =
        match.slice(1).some(
            function (part) {
                return part !== undefined;
            }
        );

    if (!hasValue) {
        return null;
    }

    const weeks = Number(
        match[1] || 0
    );

    const days = Number(
        match[2] || 0
    );

    const hours = Number(
        match[3] || 0
    );

    const minutes = Number(
        match[4] || 0
    );

    const seconds = Number(
        match[5] || 0
    );

    const total =
        weeks * 604800
        + days * 86400
        + hours * 3600
        + minutes * 60
        + seconds;

    if (
        !Number.isFinite(total)
        || total <= 0
        || total > 86400
    ) {
        return null;
    }

    return Math.round(total);
}


function formatDurationForSpeech(
    handlerInput,
    totalSeconds
) {
    let remaining = Math.max(
        0,
        Math.round(Number(totalSeconds) || 0)
    );

    const english =
        requestLanguage(handlerInput) === 'en';

    const hours = Math.floor(remaining / 3600);
    remaining %= 3600;

    const minutes = Math.floor(remaining / 60);
    const seconds = remaining % 60;
    const parts = [];

    if (hours > 0) {
        parts.push(
            hours === 1
                ? (english ? 'one hour' : 'eine Stunde')
                : hours + (english ? ' hours' : ' Stunden')
        );
    }

    if (minutes > 0) {
        parts.push(
            minutes === 1
                ? (english ? 'one minute' : 'eine Minute')
                : minutes + (english ? ' minutes' : ' Minuten')
        );
    }

    if (seconds > 0) {
        parts.push(
            seconds === 1
                ? (english ? 'one second' : 'eine Sekunde')
                : seconds + (english ? ' seconds' : ' Sekunden')
        );
    }

    if (parts.length === 0) {
        return english ? 'zero seconds' : 'null Sekunden';
    }

    if (parts.length === 1) {
        return parts[0];
    }

    return (
        parts.slice(0, -1).join(', ')
        + (english ? ' and ' : ' und ')
        + parts[parts.length - 1]
    );
}


function createStartSpeech(
    handlerInput,
    result,
    query
) {
    const queue = result.queue || {};
    const match = result.match || {};
    const english =
        requestLanguage(handlerInput) === 'en';

    if (queue.kind === 'album') {
        let speech = english
            ? 'I am playing the album '
                + (queue.title || query)
            : 'Ich spiele das Album '
                + (queue.title || query);

        if (queue.artist) {
            speech += english
                ? ' by ' + queue.artist
                : ' von ' + queue.artist;
        }

        return speech + '.';
    }

    if (queue.kind === 'artist') {
        return (
            (
                english
                    ? 'I am playing music by '
                    : 'Ich spiele Musik von '
            )
            + (
                queue.artist
                || queue.title
                || query
            )
            + '.'
        );
    }

    if (queue.kind === 'playlist') {
        return (
            (
                english
                    ? 'I am playing the playlist '
                    : 'Ich spiele die Playlist '
            )
            + (queue.title || query)
            + '.'
        );
    }

    if (queue.kind === 'random') {
        return english
            ? 'I am playing random music.'
            : 'Ich spiele zufällige Musik.';
    }

    let speech = english
        ? 'I am playing ' + (match.title || query)
        : 'Ich spiele ' + (match.title || query);

    if (match.artist) {
        speech += english
            ? ' by ' + match.artist
            : ' von ' + match.artist;
    }

    return speech + '.';
}


async function resumePlayback(
    handlerInput,
    spokenRequest
) {
    const state = getAudioPlayerState(
        handlerInput
    );

    if (!state.token) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Es gibt keine pausierte Wiedergabe.',
                        'No playback is currently paused.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    let result;

    try {
        result = await postJson(
            CURRENT_API_URL,
            {
                token: state.token
            }
        );
    } catch (error) {
        console.error(
            'Resume error:',
            error && error.stack
                ? error.stack
                : String(error)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte die Wiedergabe '
                            + 'nicht fortsetzen.',
                        'I could not resume playback.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (!resultIsPlayable(result)) {
        console.error(
            'Invalid current response:',
            JSON.stringify(result)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte die Wiedergabe '
                            + 'nicht fortsetzen.',
                        'I could not resume playback.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    console.log(
        'Resuming playback:',
        result.match.artist,
        result.match.title,
        'at',
        state.offsetInMilliseconds,
        'milliseconds'
    );

    const responseBuilder =
        handlerInput.responseBuilder
            .addDirective(
                createPlayDirective(
                    result,
                    'REPLACE_ALL',
                    '',
                    state.offsetInMilliseconds
                )
            );

    if (spokenRequest) {
        responseBuilder.withShouldEndSession(
            true
        );
    }

    return responseBuilder.getResponse();
}


async function seekAudiobookByTime(
    handlerInput,
    direction,
    seconds,
    spokenRequest
) {
    const state = getAudioPlayerState(
        handlerInput
    );

    if (!isAudiobookToken(state.token)) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Es läuft kein Hörbuch.',
                        'No audiobook is currently playing.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    let result;

    try {
        result = await postJson(
            AUDIOBOOK_SEEK_API_URL,
            {
                token: state.token,
                direction: direction,
                seconds: seconds,
                offsetInMilliseconds:
                    state.offsetInMilliseconds
            }
        );
    } catch (error) {
        console.error(
            'Seek error:',
            direction,
            seconds,
            error && error.stack
                ? error.stack
                : String(error)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte im Hörbuch '
                            + 'nicht springen.',
                        'I could not seek within '
                            + 'the audiobook.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (!resultIsPlayable(result)) {
        console.error(
            'Invalid seek response:',
            JSON.stringify(result)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte im Hörbuch '
                            + 'nicht springen.',
                        'I could not seek within '
                            + 'the audiobook.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    const playback =
        result.playback || {};

    const seek =
        result.seek || {};

    let offset = Number(
        playback.offsetInMilliseconds || 0
    );

    if (
        !Number.isFinite(offset)
        || offset < 0
    ) {
        offset = 0;
    }

    offset = Math.floor(offset);

    console.log(
        'Seeking within audiobook:',
        direction,
        seconds,
        'seconds',
        'from',
        seek.fromSeconds !== undefined
            ? seek.fromSeconds
            : '',
        'to',
        seek.toSeconds !== undefined
            ? seek.toSeconds
            : '',
        'at',
        offset,
        'milliseconds'
    );

    const responseBuilder =
        handlerInput.responseBuilder;

    if (spokenRequest) {
        const english =
            requestLanguage(handlerInput) === 'en';

        let speech;

        if (seek.boundary === 'start') {
            speech = english
                ? 'I am skipping to the beginning.'
                : 'Ich springe zum Anfang.';
        } else if (
            seek.boundary === 'end'
        ) {
            speech = english
                ? 'I am skipping to the end.'
                : 'Ich springe ans Ende.';
        } else {
            const duration =
                formatDurationForSpeech(
                    handlerInput,
                    seconds
                );

            if (english) {
                speech =
                    'I am skipping '
                    + duration
                    + (
                        direction === 'forward'
                            ? ' forward.'
                            : ' back.'
                    );
            } else {
                speech =
                    'Ich springe '
                    + duration
                    + (
                        direction === 'forward'
                            ? ' vor.'
                            : ' zurück.'
                    );
            }
        }

        responseBuilder.speak(speech);
    }

    responseBuilder.addDirective(
        createPlayDirective(
            result,
            'REPLACE_ALL',
            '',
            offset
        )
    );

    if (spokenRequest) {
        responseBuilder.withShouldEndSession(
            true
        );
    }

    return responseBuilder.getResponse();
}


async function changeAudiobookChapter(
    handlerInput,
    action,
    spokenRequest,
    chapterNumber
) {
    const state = getAudioPlayerState(
        handlerInput
    );

    if (!isAudiobookToken(state.token)) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Es läuft kein Hörbuch.',
                        'No audiobook is currently playing.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    const payload = {
        token: state.token,
        action: action,
        offsetInMilliseconds:
            state.offsetInMilliseconds
    };

    if (action === 'number') {
        payload.chapterNumber =
            chapterNumber;
    }

    let result;

    try {
        result = await postJson(
            AUDIOBOOK_CHAPTER_API_URL,
            payload
        );
    } catch (error) {
        console.error(
            'Chapter change error:',
            action,
            chapterNumber || '',
            error && error.stack
                ? error.stack
                : String(error)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte das Kapitel '
                            + 'nicht wechseln.',
                        'I could not change '
                            + 'the audiobook chapter.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (
        result
        && result.status === 'end'
    ) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Das ist bereits das '
                            + 'letzte Kapitel.',
                        'This is already '
                            + 'the last chapter.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (!resultIsPlayable(result)) {
        console.error(
            'Invalid chapter response:',
            JSON.stringify(result)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte das Kapitel '
                            + 'nicht wechseln.',
                        'I could not change '
                            + 'the audiobook chapter.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    const chapter =
        result.chapter || {};

    const playback =
        result.playback || {};

    let offset = Number(
        playback.offsetInMilliseconds || 0
    );

    if (
        !Number.isFinite(offset)
        || offset < 0
    ) {
        offset = 0;
    }

    offset = Math.floor(offset);

    console.log(
        'Starting audiobook chapter:',
        chapter.number || '',
        'of',
        chapter.count || '',
        chapter.title || '',
        'at',
        offset,
        'milliseconds'
    );

    const responseBuilder =
        handlerInput.responseBuilder;

    if (spokenRequest) {
        const english =
            requestLanguage(handlerInput) === 'en';

        let speech =
            (
                english
                    ? 'I am starting chapter '
                    : 'Ich starte Kapitel '
            )
            + (
                chapter.number
                || chapterNumber
                || ''
            );

        if (chapter.title) {
            speech +=
                ', ' + chapter.title;
        }

        speech += '.';

        responseBuilder.speak(speech);
    }

    responseBuilder.addDirective(
        createPlayDirective(
            result,
            'REPLACE_ALL',
            '',
            offset
        )
    );

    if (spokenRequest) {
        responseBuilder.withShouldEndSession(
            true
        );
    }

    return responseBuilder.getResponse();
}


async function skipToNext(
    handlerInput,
    spokenRequest
) {
    const state = getAudioPlayerState(
        handlerInput
    );

    if (!state.token) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Es läuft keine Wiedergabe.',
                        'Nothing is currently playing.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (isAudiobookToken(state.token)) {
        return changeAudiobookChapter(
            handlerInput,
            'next',
            spokenRequest
        );
    }

    let result;

    try {
        result = await postJson(
            NEXT_API_URL,
            {
                token: state.token
            }
        );
    } catch (error) {
        console.error(
            'Skip error:',
            error && error.stack
                ? error.stack
                : String(error)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte nicht zum nächsten '
                            + 'Titel springen.',
                        'I could not skip '
                            + 'to the next track.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (
        result
        && result.status === 'end'
    ) {
        console.log(
            'No further track in the queue.'
        );

        const responseBuilder =
            handlerInput.responseBuilder
                .addDirective(
                    createClearAllDirective()
                );

        if (spokenRequest) {
            responseBuilder.withShouldEndSession(
                true
            );
        }

        return responseBuilder.getResponse();
    }

    if (!resultIsPlayable(result)) {
        console.error(
            'Invalid next response:',
            JSON.stringify(result)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte nicht zum nächsten '
                            + 'Titel springen.',
                        'I could not skip '
                            + 'to the next track.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    console.log(
        'Skipping to next track:',
        result.match.artist,
        result.match.title,
        result.queue.position,
        'of',
        result.queue.count
    );

    const responseBuilder =
        handlerInput.responseBuilder
            .addDirective(
                createPlayDirective(
                    result,
                    'REPLACE_ALL',
                    '',
                    0
                )
            );

    if (spokenRequest) {
        responseBuilder.withShouldEndSession(
            true
        );
    }

    return responseBuilder.getResponse();
}

async function goToPrevious(
    handlerInput,
    spokenRequest
) {
    const state = getAudioPlayerState(
        handlerInput
    );

    if (!state.token) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Es läuft keine Wiedergabe.',
                        'Nothing is currently playing.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (isAudiobookToken(state.token)) {
        return changeAudiobookChapter(
            handlerInput,
            'previous',
            spokenRequest
        );
    }

    /**
     * Common music-player behavior:
     *
     * After more than five seconds, the current track
     * is restarted from the beginning.
     *
     * Within the first five seconds, playback switches
     * to the previous track.
     */
    const restartCurrent =
        state.offsetInMilliseconds > 5000;

    const apiUrl =
        restartCurrent
            ? CURRENT_API_URL
            : PREVIOUS_API_URL;

    let result;

    try {
        result = await postJson(
            apiUrl,
            {
                token: state.token
            }
        );
    } catch (error) {
        console.error(
            'Previous-track error:',
            error && error.stack
                ? error.stack
                : String(error)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte nicht zum vorherigen '
                            + 'Titel wechseln.',
                        'I could not go '
                            + 'to the previous track.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (!resultIsPlayable(result)) {
        console.error(
            'Invalid previous response:',
            JSON.stringify(result)
        );

        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte nicht zum vorherigen '
                            + 'Titel wechseln.',
                        'I could not go '
                            + 'to the previous track.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    if (restartCurrent) {
        console.log(
            'Restarting current track:',
            result.match.artist,
            result.match.title
        );
    } else {
        console.log(
            'Skipping to previous track:',
            result.match.artist,
            result.match.title,
            result.queue.position,
            'of',
            result.queue.count
        );
    }

    const responseBuilder =
        handlerInput.responseBuilder
            .addDirective(
                createPlayDirective(
                    result,
                    'REPLACE_ALL',
                    '',
                    0
                )
            );

    if (spokenRequest) {
        responseBuilder.withShouldEndSession(
            true
        );
    }

    return responseBuilder.getResponse();
}

function requestLanguage(handlerInput) {
    const locale = String(
        handlerInput.requestEnvelope.request.locale || 'de-DE'
    ).toLowerCase();

    return locale.startsWith('en') ? 'en' : 'de';
}

function localizedText(
    handlerInput,
    germanText,
    englishText
) {
    return requestLanguage(handlerInput) === 'en'
        ? englishText
        : germanText;
}

const LaunchRequestHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'LaunchRequest';
    },

    handle(handlerInput) {
        const text = localizedText(
            handlerInput,
            'Was möchtest du hören? '
                + 'Du kannst einen Titel, '
                + 'ein Album oder einen Künstler nennen.',
            'What would you like to listen to? '
                + 'You can name a song, '
                + 'an album, or an artist.'
        );

        const reprompt = localizedText(
            handlerInput,
            'Sage zum Beispiel: '
                + 'Spiele Bosco, '
                + 'spiele das Album Loud Like Love '
                + 'oder spiele Musik von Placebo.',
            'For example, say: '
                + 'Play Bosco, '
                + 'play the album Loud Like Love, '
                + 'or play music by Placebo.'
        );

        return handlerInput.responseBuilder
            .speak(text)
            .reprompt(reprompt)
            .getResponse();
    }
};

const PlayAudiobookIntentHandler = {
    canHandle(handlerInput) {
        if (
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            ) !== 'IntentRequest'
        ) {
            return false;
        }

        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return [
            'PlayAudiobookIntent',
            'PlayAudiobookFromStartIntent',
            'PlayRandomAudiobookIntent'
        ].indexOf(intentName) !== -1;
    },

    async handle(handlerInput) {
        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        const randomSeries =
            intentName
            === 'PlayRandomAudiobookIntent';

        const fromStart =
            intentName
            === 'PlayAudiobookFromStartIntent';

        const query = getSlotValue(
            handlerInput,
            'Query'
        );

        let result;

        if (
            randomSeries
            && !query
        ) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Von welcher Hörspielserie möchtest '
                            + 'du eine zufällige Folge hören?',
                        'Which audiobook series would you like '
                            + 'a random audiobook from?'
                    )
                )
                .reprompt(
                    localizedText(
                        handlerInput,
                        'Sage zum Beispiel: Spiele ein '
                            + 'zufälliges Hörspiel von '
                            + 'Benjamin Blümchen.',
                        'For example, say: Play a random '
                            + 'audiobook from Harry Potter.'
                    )
                )
                .getResponse();
        }


        if (
            fromStart
            && !query
        ) {
            const state = getAudioPlayerState(
                handlerInput
            );

            if (!isAudiobookToken(state.token)) {
                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Welches Hörbuch möchtest '
                                + 'du von vorne hören?',
                            'Which audiobook would you like '
                                + 'to play from the beginning?'
                        )
                    )
                    .reprompt(
                        localizedText(
                            handlerInput,
                            'Sage zum Beispiel: '
                                + 'Spiele Benjamin rettet '
                                + 'den Zoo von vorne ab.',
                            'For example, say: '
                                + 'Play Benjamin rettet den Zoo '
                                + 'from the beginning.'
                        )
                    )
                    .getResponse();
            }

            console.log(
                'Restarting current audiobook from the beginning:',
                state.token
            );

            try {
                result = await postJson(
                    AUDIOBOOK_RESTART_API_URL,
                    {
                        token: state.token
                    }
                );
            } catch (error) {
                console.error(
                    'Audiobookshelf restart error:',
                    error && error.stack
                        ? error.stack
                        : String(error)
                );

                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Ich konnte das Hörbuch '
                                + 'gerade nicht von vorne starten.',
                            'I could not restart '
                                + 'the audiobook right now.'
                        )
                    )
                    .withShouldEndSession(true)
                    .getResponse();
            }
        } else {
            if (!query) {
                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Welches Hörbuch möchtest du hören?',
                            'Which audiobook would you like '
                                + 'to listen to?'
                        )
                    )
                    .reprompt(
                        localizedText(
                            handlerInput,
                            'Sage zum Beispiel: '
                                + 'Spiele das Hörbuch '
                                + 'Benjamin rettet den Zoo.',
                            'For example, say: '
                                + 'Play the audiobook '
                                + 'Benjamin rettet den Zoo.'
                        )
                    )
                    .getResponse();
            }

            console.log(
                randomSeries
                    ? 'Audiobookshelf random series search:'
                    : fromStart
                        ? 'Audiobookshelf search from the beginning:'
                        : 'Audiobookshelf search:',
                query
            );

            try {
                result = await postJson(
                    AUDIOBOOK_RESOLVE_API_URL,
                    {
                        query: query,
                        fromStart: fromStart,
                        randomSeries: randomSeries
                    }
                );
            } catch (error) {
                console.error(
                    'Audiobookshelf resolver error:',
                    error && error.stack
                        ? error.stack
                        : String(error)
                );

                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Ich konnte Audiobookshelf '
                                + 'gerade nicht erreichen.',
                            'I could not reach Audiobookshelf '
                                + 'right now.'
                        )
                    )
                    .withShouldEndSession(true)
                    .getResponse();
            }
        }

        if (!resultIsPlayable(result)) {
            console.error(
                'Invalid audiobook response:',
                JSON.stringify(result)
            );

            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich habe kein passendes '
                            + 'Hörbuch gefunden.',
                        'I could not find '
                            + 'a matching audiobook.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        const match =
            result.match || {};

        const playback =
            result.playback || {};

        let offset = Number(
            playback.offsetInMilliseconds || 0
        );

        if (
            !Number.isFinite(offset)
            || offset < 0
            || fromStart
        ) {
            offset = 0;
        }

        offset = Math.floor(offset);

        const english =
            requestLanguage(handlerInput) === 'en';

        const title =
            match.title
            || query
            || '';

        let speech;

        if (fromStart) {
            speech = english
                ? 'I am starting '
                    + (title || 'the audiobook')
                    + ' from the beginning'
                : 'Ich starte '
                    + (title || 'das Hörbuch')
                    + ' von vorne';

            if (match.author) {
                speech += english
                    ? ' by ' + match.author
                    : ' von ' + match.author;
            }

            speech += '.';
        } else if (offset > 5000) {
            speech = english
                ? 'I am resuming '
                    + (title || 'the audiobook')
                : 'Ich setze '
                    + (title || 'das Hörbuch')
                    + ' fort';

            if (match.author) {
                speech += english
                    ? ' by ' + match.author
                    : ' von ' + match.author;
            }

            speech += '.';
        } else {
            if (english) {
                speech = title
                    ? 'I am playing the audiobook ' + title
                    : 'I am playing an audiobook';
            } else {
                speech = title
                    ? 'Ich spiele das Hörbuch ' + title
                    : 'Ich spiele ein Hörbuch';
            }

            if (match.author) {
                speech += english
                    ? ' by ' + match.author
                    : ' von ' + match.author;
            }

            speech += '.';
        }

        console.log(
            fromStart
                ? 'Starting audiobook from the beginning:'
                : 'Starting audiobook:',
            match.author || '',
            match.title || query,
            'at',
            offset,
            'milliseconds',
            'chapter count:',
            match.chapterCount || 0
        );

        return handlerInput.responseBuilder
            .speak(speech)
            .addDirective(
                createPlayDirective(
                    result,
                    'REPLACE_ALL',
                    '',
                    offset
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }
};


function parseMisroutedRandomUnheardAudiobookQuery(
    handlerInput,
    value
) {
    const text = String(
        value || ''
    )
        .trim()
        .replace(/\s+/g, ' ')
        .replace(/[.!?]+$/g, '');

    if (!text) {
        return '';
    }

    const language =
        requestLanguage(handlerInput);

    const patterns =
        language === 'en'
            ? [
                /^(?:an?\s+)?(?:random\s+)?unheard\s+episode\s+(?:of|from)\s+(.+)$/i,
                /^(?:an?\s+)?(?:random\s+)?unheard\s+audiobook\s+(?:of|from)\s+(.+)$/i
            ]
            : [
                /^(?:eine\s+)?(?:zufällige\s+)?ungehörte\s+folge\s+von\s+(.+)$/i,
                /^(?:ein\s+)?(?:zufälliges\s+)?ungehörtes\s+hörspiel\s+von\s+(.+)$/i
            ];

    for (const pattern of patterns) {
        const match =
            pattern.exec(text);

        if (
            match
            && match[1]
            && match[1].trim()
        ) {
            return match[1].trim();
        }
    }

    return '';
}


const PlayMediaIntentHandler = {
    canHandle(handlerInput) {
        if (
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            ) !== 'IntentRequest'
        ) {
            return false;
        }

        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return [
            'PlaySongIntent',
            'PlayAlbumIntent',
            'PlayArtistIntent',
            'PlayPlaylistIntent',
            'PlayRandomIntent'
        ].indexOf(intentName) !== -1;
    },

    async handle(handlerInput) {
        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        const mode = getModeForIntent(
            intentName
        );

        let query = '';

        if (mode !== 'random') {
            query = getSlotValue(
                handlerInput,
                'Query'
            );
        }

        /*
         * Real Alexa devices can occasionally route
         * an unheard-audiobook request to the broad
         * PlaySongIntent. Catch that phrase before
         * it reaches Navidrome and reroute it to
         * Audiobookshelf.
         */
        const misroutedUnheardQuery =
            mode !== 'random'
                ? parseMisroutedRandomUnheardAudiobookQuery(
                    handlerInput,
                    query
                )
                : '';

        if (misroutedUnheardQuery) {
            console.log(
                'Rerouting media intent to '
                    + 'random unheard audiobook:',
                intentName,
                query,
                '=>',
                misroutedUnheardQuery
            );

            let audiobookResult;

            try {
                audiobookResult = await postJson(
                    AUDIOBOOK_RESOLVE_API_URL,
                    {
                        query:
                            misroutedUnheardQuery,
                        randomUnheardSeries: true
                    }
                );
            } catch (error) {
                console.error(
                    'Rerouted audiobook resolver error:',
                    error && error.stack
                        ? error.stack
                        : String(error)
                );

                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Ich konnte das gewünschte '
                                + 'Hörbuch gerade nicht starten.',
                            'I could not start the requested '
                                + 'audiobook right now.'
                        )
                    )
                    .withShouldEndSession(true)
                    .getResponse();
            }

            if (
                !resultIsPlayable(
                    audiobookResult
                )
            ) {
                console.error(
                    'Invalid rerouted audiobook response:',
                    JSON.stringify(
                        audiobookResult
                    )
                );

                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Ich habe keine passende '
                                + 'ungehörte Folge gefunden.',
                            'I could not find a matching '
                                + 'unheard episode.'
                        )
                    )
                    .withShouldEndSession(true)
                    .getResponse();
            }

            const audiobookMatch =
                audiobookResult.match || {};

            const audiobookSelection =
                audiobookResult.selection || {};

            const seriesName =
                audiobookSelection.seriesName
                || misroutedUnheardQuery;

            const title =
                audiobookMatch.title
                || '';

            let speech =
                localizedText(
                    handlerInput,
                    'Ich habe zufällig eine ungehörte '
                        + 'Folge von '
                        + seriesName
                        + ' ausgewählt',
                    'I randomly selected an unheard '
                        + 'episode of '
                        + seriesName
                );

            if (title) {
                speech +=
                    localizedText(
                        handlerInput,
                        ': ' + title,
                        ': ' + title
                    );
            }

            speech += '.';

            return handlerInput.responseBuilder
                .speak(speech)
                .addDirective(
                    createPlayDirective(
                        audiobookResult,
                        'REPLACE_ALL',
                        '',
                        0
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        if (
            mode !== 'random'
            && !query
        ) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Was möchtest du hören?',
                        'What would you like to listen to?'
                    )
                )
                .reprompt(
                    localizedText(
                        handlerInput,
                        'Nenne bitte einen Titel, '
                            + 'ein Album, einen Künstler '
                            + 'oder eine Playlist.',
                        'Please name a song, an album, '
                            + 'an artist, or a playlist.'
                    )
                )
                .getResponse();
        }

        console.log(
            'Navidrome search:',
            mode,
            query
        );

        let result;

        try {
            result = await postJson(
                RESOLVE_API_URL,
                {
                    query: query,
                    mode: mode
                }
            );
        } catch (error) {
            console.error(
                'Resolver error:',
                error && error.stack
                    ? error.stack
                    : String(error)
            );

            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte Navidrome gerade '
                            + 'nicht erreichen.',
                        'I could not reach Navidrome '
                            + 'right now.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        if (!resultIsPlayable(result)) {
            console.error(
                'Invalid resolver response:',
                JSON.stringify(result)
            );

            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich habe nichts Passendes gefunden.',
                        'I could not find anything matching that.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        console.log(
            'Starting playback:',
            result.queue.kind,
            result.match.artist,
            result.match.title,
            result.queue.position,
            'of',
            result.queue.count
        );

        return handlerInput.responseBuilder
            .speak(
                createStartSpeech(handlerInput, result, query)
            )
            .addDirective(
                createPlayDirective(
                    result,
                    'REPLACE_ALL',
                    '',
                    0
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }
};


const PauseIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'AMAZON.PauseIntent';
    },

    handle(handlerInput) {
        console.log(
            'Pausing playback.'
        );

        return handlerInput.responseBuilder
            .addDirective({
                type: 'AudioPlayer.Stop'
            })
            .withShouldEndSession(true)
            .getResponse();
    }
};


const ResumeIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'AMAZON.ResumeIntent';
    },

    async handle(handlerInput) {
        return resumePlayback(
            handlerInput,
            true
        );
    }
};



async function changeAudiobookSeriesEpisode(
    handlerInput,
    direction,
    spokenRequest
) {
    const state = getAudioPlayerState(
        handlerInput
    );

    if (!isAudiobookToken(state.token)) {
        if (spokenRequest) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Es läuft kein Hörbuch.',
                        'No audiobook is currently playing.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        return handlerInput.responseBuilder
            .getResponse();
    }

    let result;

    try {
        result = await postJson(
            AUDIOBOOK_SERIES_NEIGHBOR_API_URL,
            {
                token: state.token,
                direction: direction,
                offsetInMilliseconds:
                    state.offsetInMilliseconds
            }
        );
    } catch (error) {
        console.error(
            'Audiobook series change error:',
            direction,
            error && error.stack
                ? error.stack
                : String(error)
        );

        return handlerInput.responseBuilder
            .speak(
                localizedText(
                    handlerInput,
                    'Ich konnte die Folge gerade '
                        + 'nicht wechseln.',
                    'I could not change the episode '
                        + 'right now.'
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }

    if (
        result
        && result.status === 'end'
    ) {
        const atEnd =
            direction === 'next';

        return handlerInput.responseBuilder
            .speak(
                localizedText(
                    handlerInput,
                    atEnd
                        ? 'Das ist bereits die letzte '
                            + 'Folge der Serie.'
                        : 'Das ist bereits die erste '
                            + 'Folge der Serie.',
                    atEnd
                        ? 'This is already the last '
                            + 'episode in the series.'
                        : 'This is already the first '
                            + 'episode in the series.'
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }

    if (!resultIsPlayable(result)) {
        console.error(
            'Invalid audiobook series response:',
            JSON.stringify(result)
        );

        return handlerInput.responseBuilder
            .speak(
                localizedText(
                    handlerInput,
                    'Ich konnte die Folge gerade '
                        + 'nicht wechseln.',
                    'I could not change the episode '
                        + 'right now.'
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }

    const match =
        result.match || {};

    const selection =
        result.selection || {};

    let speech;

    if (direction === 'next') {
        speech = localizedText(
            handlerInput,
            'Ich spiele die nächste Folge',
            'I am playing the next episode'
        );
    } else {
        speech = localizedText(
            handlerInput,
            'Ich spiele die vorherige Folge',
            'I am playing the previous episode'
        );
    }

    if (selection.sequence) {
        speech += localizedText(
            handlerInput,
            ', Folge ',
            ', episode '
        ) + selection.sequence;
    }

    if (match.title) {
        speech += ', ' + match.title;
    }

    speech += '.';

    console.log(
        'Starting audiobook series neighbor:',
        direction,
        selection.seriesName || '',
        selection.sequence || '',
        match.title || ''
    );

    return handlerInput.responseBuilder
        .speak(speech)
        .addDirective(
            createPlayDirective(
                result,
                'REPLACE_ALL',
                '',
                0
            )
        )
        .withShouldEndSession(true)
        .getResponse();
}


const AudiobookSelectionIntentHandler = {
    canHandle(handlerInput) {
        if (
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            ) !== 'IntentRequest'
        ) {
            return false;
        }

        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return [
            'PlayAudiobookSeriesEpisodeIntent',
            'PlayRandomLibraryAudiobookIntent',
            'PlayRandomUnheardAudiobookIntent'
        ].indexOf(intentName) !== -1;
    },

    async handle(handlerInput) {
        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        const payload = {};

        let query = '';
        let episodeNumber = '';
        let forceFromStart = false;

        if (
            intentName
            === 'PlayAudiobookSeriesEpisodeIntent'
        ) {
            const spokenQuery = getSlotValue(
                handlerInput,
                'Query'
            );

            const parsed =
                parseAudiobookSeriesEpisodeQuery(
                    handlerInput,
                    spokenQuery
                );

            if (!parsed) {
                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Welche Folge aus welcher Serie '
                                + 'möchtest du hören?',
                            'Which episode from which series '
                                + 'would you like to hear?'
                        )
                    )
                    .reprompt(
                        localizedText(
                            handlerInput,
                            'Sage zum Beispiel: '
                                + 'Spiele Folge zweiundvierzig '
                                + 'von Benjamin Blümchen.',
                            'For example, say: '
                                + 'Play episode forty two '
                                + 'of Harry Potter.'
                        )
                    )
                    .getResponse();
            }

            query = parsed.query;
            episodeNumber =
                parsed.episodeNumber;

            console.log(
                'Parsed audiobook series episode query:',
                spokenQuery,
                '=>',
                episodeNumber,
                query
            );

            payload.query = query;
            payload.episodeNumber =
                episodeNumber;
        } else if (
            intentName
            === 'PlayRandomLibraryAudiobookIntent'
        ) {
            payload.randomLibrary = true;
            forceFromStart = true;
        } else {
            query = getSlotValue(
                handlerInput,
                'Query'
            );

            if (!query) {
                return handlerInput.responseBuilder
                    .speak(
                        localizedText(
                            handlerInput,
                            'Von welcher Hörspielserie '
                                + 'möchtest du eine '
                                + 'ungehörte Folge hören?',
                            'Which audiobook series '
                                + 'would you like an '
                                + 'unheard episode from?'
                        )
                    )
                    .reprompt(
                        localizedText(
                            handlerInput,
                            'Sage zum Beispiel: '
                                + 'Spiele eine ungehörte Folge '
                                + 'von Benjamin Blümchen.',
                            'For example, say: '
                                + 'Play an unheard episode '
                                + 'of Harry Potter.'
                        )
                    )
                    .getResponse();
            }

            payload.query = query;
            payload.randomUnheardSeries = true;
            forceFromStart = true;
        }

        let result;

        try {
            result = await postJson(
                AUDIOBOOK_RESOLVE_API_URL,
                payload
            );
        } catch (error) {
            console.error(
                'Audiobook selection error:',
                intentName,
                error && error.stack
                    ? error.stack
                    : String(error)
            );

            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich konnte das gewünschte '
                            + 'Hörbuch gerade nicht starten.',
                        'I could not start the requested '
                            + 'audiobook right now.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        if (!resultIsPlayable(result)) {
            console.error(
                'Invalid audiobook selection response:',
                JSON.stringify(result)
            );

            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Ich habe kein passendes '
                            + 'Hörbuch gefunden.',
                        'I could not find a matching '
                            + 'audiobook.'
                    )
                )
                .withShouldEndSession(true)
                .getResponse();
        }

        const match =
            result.match || {};

        const playback =
            result.playback || {};

        const selection =
            result.selection || {};

        let offset = Number(
            playback.offsetInMilliseconds || 0
        );

        if (
            !Number.isFinite(offset)
            || offset < 0
            || forceFromStart
        ) {
            offset = 0;
        }

        offset = Math.floor(offset);

        const title =
            match.title
            || query
            || '';

        let speech;

        if (
            intentName
            === 'PlayAudiobookSeriesEpisodeIntent'
        ) {
            const sequence =
                selection.sequence
                || episodeNumber;

            const seriesName =
                selection.seriesName
                || query;

            speech = localizedText(
                handlerInput,
                'Ich spiele Folge '
                    + sequence
                    + ' von '
                    + seriesName,
                'I am playing episode '
                    + sequence
                    + ' of '
                    + seriesName
            );

            if (title) {
                speech += ', ' + title;
            }

            speech += '.';
        } else if (
            intentName
            === 'PlayRandomLibraryAudiobookIntent'
        ) {
            speech = localizedText(
                handlerInput,
                'Ich habe zufällig '
                    + title
                    + ' ausgewählt.',
                'I randomly selected '
                    + title
                    + '.'
            );
        } else {
            const seriesName =
                selection.seriesName
                || query;

            speech = localizedText(
                handlerInput,
                'Ich habe zufällig eine '
                    + 'ungehörte Folge von '
                    + seriesName
                    + ' ausgewählt: '
                    + title
                    + '.',
                'I randomly selected an '
                    + 'unheard episode of '
                    + seriesName
                    + ': '
                    + title
                    + '.'
            );
        }

        console.log(
            'Starting audiobook selection:',
            intentName,
            selection.seriesName || '',
            selection.sequence || '',
            match.title || '',
            'at',
            offset,
            'milliseconds'
        );

        return handlerInput.responseBuilder
            .speak(speech)
            .addDirective(
                createPlayDirective(
                    result,
                    'REPLACE_ALL',
                    '',
                    offset
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }
};


const AudiobookSeriesNeighborIntentHandler = {
    canHandle(handlerInput) {
        if (
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            ) !== 'IntentRequest'
        ) {
            return false;
        }

        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return [
            'NextAudiobookEpisodeIntent',
            'PreviousAudiobookEpisodeIntent'
        ].indexOf(intentName) !== -1;
    },

    async handle(handlerInput) {
        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return changeAudiobookSeriesEpisode(
            handlerInput,
            intentName
                === 'NextAudiobookEpisodeIntent'
                ? 'next'
                : 'previous',
            true
        );
    }
};


const AudiobookTimeSeekIntentHandler = {
    canHandle(handlerInput) {
        if (
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            ) !== 'IntentRequest'
        ) {
            return false;
        }

        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return [
            'SeekAudiobookForwardIntent',
            'SeekAudiobookBackwardIntent'
        ].indexOf(intentName) !== -1;
    },

    async handle(handlerInput) {
        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        const direction =
            intentName
            === 'SeekAudiobookForwardIntent'
                ? 'forward'
                : 'backward';

        const durationText = getSlotValue(
            handlerInput,
            'Duration'
        );

        const seconds =
            parseIsoDurationSeconds(
                durationText
            );

        if (seconds === null) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Wie weit soll ich springen?',
                        'How far should I skip?'
                    )
                )
                .reprompt(
                    localizedText(
                        handlerInput,
                        'Sage zum Beispiel: '
                            + 'Springe dreißig Sekunden vor.',
                        'For example, say: '
                            + 'Skip forward thirty seconds.'
                    )
                )
                .getResponse();
        }

        return seekAudiobookByTime(
            handlerInput,
            direction,
            seconds,
            true
        );
    }
};


const AudiobookChapterNumberIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'PlayAudiobookChapterIntent';
    },

    async handle(handlerInput) {
        const chapterText = getSlotValue(
            handlerInput,
            'ChapterNumber'
        );

        const chapterNumber = Number(
            chapterText
        );

        if (
            !Number.isInteger(
                chapterNumber
            )
            || chapterNumber < 1
        ) {
            return handlerInput.responseBuilder
                .speak(
                    localizedText(
                        handlerInput,
                        'Welche Kapitelnummer '
                            + 'möchtest du hören?',
                        'Which chapter number '
                            + 'would you like to hear?'
                    )
                )
                .reprompt(
                    localizedText(
                        handlerInput,
                        'Sage zum Beispiel: '
                            + 'Starte Kapitel drei.',
                        'For example, say: '
                            + 'Start chapter three.'
                    )
                )
                .getResponse();
        }

        return changeAudiobookChapter(
            handlerInput,
            'number',
            true,
            chapterNumber
        );
    }
};


const NextAudiobookChapterIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'NextAudiobookChapterIntent';
    },

    async handle(handlerInput) {
        return changeAudiobookChapter(
            handlerInput,
            'next',
            true
        );
    }
};


const PreviousAudiobookChapterIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'PreviousAudiobookChapterIntent';
    },

    async handle(handlerInput) {
        return changeAudiobookChapter(
            handlerInput,
            'previous',
            true
        );
    }
};


const NextIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'AMAZON.NextIntent';
    },

    async handle(handlerInput) {
        return skipToNext(
            handlerInput,
            true
        );
    }
};

const PreviousIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'AMAZON.PreviousIntent';
    },

    async handle(handlerInput) {
        return goToPrevious(
            handlerInput,
            true
        );
    }
};

const PlaybackControllerPauseHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'PlaybackController.PauseCommandIssued';
    },

    handle(handlerInput) {
        console.log(
            'Pausing via playback controller.'
        );

        return handlerInput.responseBuilder
            .addDirective({
                type: 'AudioPlayer.Stop'
            })
            .getResponse();
    }
};


const PlaybackControllerPlayHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'PlaybackController.PlayCommandIssued';
    },

    async handle(handlerInput) {
        return resumePlayback(
            handlerInput,
            false
        );
    }
};


const PlaybackControllerNextHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'PlaybackController.NextCommandIssued';
    },

    async handle(handlerInput) {
        return skipToNext(
            handlerInput,
            false
        );
    }
};

const PlaybackControllerPreviousHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'PlaybackController.PreviousCommandIssued';
    },

    async handle(handlerInput) {
        return goToPrevious(
            handlerInput,
            false
        );
    }
};

const StopCancelIntentHandler = {
    canHandle(handlerInput) {
        if (
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            ) !== 'IntentRequest'
        ) {
            return false;
        }

        const intentName =
            Alexa.getIntentName(
                handlerInput.requestEnvelope
            );

        return [
            'AMAZON.StopIntent',
            'AMAZON.CancelIntent'
        ].indexOf(intentName) !== -1;
    },

    handle(handlerInput) {
        console.log(
            'Stopping playback and clearing queue.'
        );

        return handlerInput.responseBuilder
            .addDirective(
                createClearAllDirective()
            )
            .withShouldEndSession(true)
            .getResponse();
    }
};


const PlaybackNearlyFinishedHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'AudioPlayer.PlaybackNearlyFinished';
    },

    async handle(handlerInput) {
        const request =
            handlerInput.requestEnvelope.request || {};

        const currentToken =
            String(request.token || '');

        if (isAudiobookToken(currentToken)) {
            console.log(
                'Audiobook end reached; '
                + 'no further track will be enqueued.'
            );

            return handlerInput.responseBuilder
            .getResponse();
        }

        if (!currentToken) {
            console.error(
                'PlaybackNearlyFinished without token.'
            );

            return handlerInput.responseBuilder
                .getResponse();
        }

        let result;

        try {
            result = await postJson(
                NEXT_API_URL,
                {
                    token: currentToken
                }
            );
        } catch (error) {
            console.error(
                'Next error:',
                error && error.stack
                    ? error.stack
                    : String(error)
            );

            return handlerInput.responseBuilder
                .getResponse();
        }

        if (
            result
            && result.status === 'end'
        ) {
            console.log(
                'Queue ended:',
                result.queue
                    ? result.queue.title
                    : ''
            );

            return handlerInput.responseBuilder
                .getResponse();
        }

        if (!resultIsPlayable(result)) {
            console.error(
                'Invalid next response:',
                JSON.stringify(result)
            );

            return handlerInput.responseBuilder
                .getResponse();
        }

        console.log(
            'Enqueuing next track:',
            result.match.artist,
            result.match.title,
            result.queue.position,
            'of',
            result.queue.count
        );

        return handlerInput.responseBuilder
            .addDirective(
                createPlayDirective(
                    result,
                    'ENQUEUE',
                    currentToken,
                    0
                )
            )
            .getResponse();
    }
};


const HelpIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'AMAZON.HelpIntent';
    },

    handle(handlerInput) {
        const text = localizedText(
            handlerInput,
            'Sage zum Beispiel: '
                + 'Spiele Bosco, '
                + 'spiele das Album Loud Like Love '
                + 'oder spiele Musik von Placebo. '
                + 'Während der Wiedergabe kannst du '
                + 'Pause, Fortsetzen, nächster Titel '
                + 'oder Stopp sagen.',
            'For example, say: '
                + 'Play Bosco, '
                + 'play the album Loud Like Love, '
                + 'or play music by Placebo. '
                + 'During playback, you can say '
                + 'pause, resume, next track, or stop.'
        );

        return handlerInput.responseBuilder
            .speak(text)
            .reprompt(text)
            .getResponse();
    }
};


const FallbackIntentHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'IntentRequest'
            && Alexa.getIntentName(
                handlerInput.requestEnvelope
            ) === 'AMAZON.FallbackIntent';
    },

    handle(handlerInput) {
        const speech = localizedText(
            handlerInput,
            'Das habe ich nicht verstanden. '
                + 'Nenne bitte einen Titel, '
                + 'ein Album oder einen Künstler.',
            'I did not understand that. '
                + 'Please name a song, '
                + 'an album, or an artist.'
        );

        const reprompt = localizedText(
            handlerInput,
            'Was möchtest du hören?',
            'What would you like to listen to?'
        );

        return handlerInput.responseBuilder
            .speak(speech)
            .reprompt(reprompt)
            .getResponse();
    }
};



const PlaybackStoppedProgressHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'AudioPlayer.PlaybackStopped';
    },

    async handle(handlerInput) {
        const request =
            handlerInput.requestEnvelope.request || {};

        const token =
            String(request.token || '');

        const offset =
            request.offsetInMilliseconds || 0;

        console.log(
            'PlaybackStopped:',
            token,
            offset
        );

        await sendAudiobookProgress(
            token,
            'stopped',
            offset
        );

        return handlerInput.responseBuilder
            .getResponse();
    }
};


const AudioPlayerEventHandler = {
    canHandle(handlerInput) {
        const requestType =
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            );

        return requestType.indexOf(
            'AudioPlayer.'
        ) === 0;
    },

    handle(handlerInput) {
        const request =
            handlerInput.requestEnvelope.request || {};

        console.log(
            'AudioPlayer event:',
            request.type,
            request.token || '',
            request.offsetInMilliseconds || 0
        );

        if (request.error) {
            console.error(
                'AudioPlayer error:',
                JSON.stringify(
                    request.error,
                    null,
                    2
                )
            );
        }

        return handlerInput.responseBuilder
            .getResponse();
    }
};

const PlaybackStartedScrobbleHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'AudioPlayer.PlaybackStarted';
    },

    async handle(handlerInput) {
        const request =
            handlerInput.requestEnvelope.request || {};

        const token =
            String(request.token || '');

        console.log(
            'PlaybackStarted:',
            token,
            request.offsetInMilliseconds || 0
        );

        await sendScrobble(
            token,
            'started'
        );

        return handlerInput.responseBuilder
            .getResponse();
    }
};


const PlaybackFinishedScrobbleHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'AudioPlayer.PlaybackFinished';
    },

    async handle(handlerInput) {
        const request =
            handlerInput.requestEnvelope.request || {};

        const token =
            String(request.token || '');

        console.log(
            'PlaybackFinished:',
            token,
            request.offsetInMilliseconds || 0
        );

        if (isAudiobookToken(token)) {
            await sendAudiobookProgress(
                token,
                'finished',
                request.offsetInMilliseconds || 0
            );
        } else {
            await sendScrobble(
                token,
                'finished'
            );
        }

        return handlerInput.responseBuilder
            .getResponse();
    }
};

const SystemExceptionHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'System.ExceptionEncountered';
    },

    handle(handlerInput) {
        console.error(
            'System.ExceptionEncountered:',
            JSON.stringify(
                handlerInput.requestEnvelope.request,
                null,
                2
            )
        );

        return handlerInput.responseBuilder
            .getResponse();
    }
};


const SessionEndedRequestHandler = {
    canHandle(handlerInput) {
        return Alexa.getRequestType(
            handlerInput.requestEnvelope
        ) === 'SessionEndedRequest';
    },

    handle(handlerInput) {
        const request =
            handlerInput.requestEnvelope.request || {};

        console.log(
            'Session ended:',
            request.reason || ''
        );

        if (request.error) {
            console.error(
                'Session error:',
                JSON.stringify(
                    request.error,
                    null,
                    2
                )
            );
        }

        return handlerInput.responseBuilder
            .getResponse();
    }
};


const ErrorHandler = {
    canHandle() {
        return true;
    },

    handle(handlerInput, error) {
        const requestType =
            Alexa.getRequestType(
                handlerInput.requestEnvelope
            );

        console.error(
            'Skill error:',
            error && error.stack
                ? error.stack
                : String(error)
        );

        if (
            requestType.indexOf(
                'AudioPlayer.'
            ) === 0
            || requestType.indexOf(
                'PlaybackController.'
            ) === 0
        ) {
            return handlerInput.responseBuilder
                .getResponse();
        }

        return handlerInput.responseBuilder
            .speak(
                localizedText(
                    handlerInput,
                    'Beim Abspielen ist ein Fehler aufgetreten.',
                    'An error occurred during playback.'
                )
            )
            .withShouldEndSession(true)
            .getResponse();
    }
};


const skill = Alexa.SkillBuilders
    .custom()
    .addRequestHandlers(
        SystemExceptionHandler,
        PlaybackNearlyFinishedHandler,
        PlaybackStartedScrobbleHandler,
        PlaybackFinishedScrobbleHandler,
        PlaybackStoppedProgressHandler,
        AudioPlayerEventHandler,
        PlaybackControllerPauseHandler,
        PlaybackControllerPlayHandler,
        PlaybackControllerNextHandler,
        PlaybackControllerPreviousHandler,
        LaunchRequestHandler,
        PlayAudiobookIntentHandler,
        AudiobookSelectionIntentHandler,
        AudiobookSeriesNeighborIntentHandler,
        AudiobookTimeSeekIntentHandler,
        AudiobookChapterNumberIntentHandler,
        NextAudiobookChapterIntentHandler,
        PreviousAudiobookChapterIntentHandler,
        PlayMediaIntentHandler,
        PauseIntentHandler,
        ResumeIntentHandler,
        NextIntentHandler,
        PreviousIntentHandler,
        StopCancelIntentHandler,
        HelpIntentHandler,
        FallbackIntentHandler,
        SessionEndedRequestHandler
    )
    .addErrorHandlers(
        ErrorHandler
    )
    .create();

exports.handler = async (event, context) => {
    return skill.invoke(event, context);
};
