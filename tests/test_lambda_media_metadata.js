'use strict';

const fs = require('fs');
const https = require('https');
const path = require('path');
const { EventEmitter } = require('events');


process.env.BRIDGE_BASE_URL =
    'https://media.example.com';

process.env.CONTROL_SECRET =
    '0123456789abcdef0123456789abcdef';


const ROOT = path.resolve(
    __dirname,
    '..'
);

const EVENT_PATH = path.join(
    ROOT,
    'skill',
    'test_events',
    'play_song_de_DE.json'
);

let bridgePayload = null;


https.request = function (
    options,
    callback
) {
    const request =
        new EventEmitter();

    request.setTimeout =
        function () {};

    request.write =
        function () {};

    request.destroy =
        function (error) {
            if (error) {
                request.emit(
                    'error',
                    error
                );
            }
        };

    request.end =
        function () {
            const response =
                new EventEmitter();

            response.statusCode = 200;

            response.setEncoding =
                function () {};

            callback(response);

            process.nextTick(
                function () {
                    response.emit(
                        'data',
                        JSON.stringify(
                            bridgePayload
                        )
                    );

                    response.emit('end');
                }
            );
        };

    return request;
};


const { handler } = require(
    path.join(
        ROOT,
        'skill',
        'lambda',
        'index.js'
    )
);


function loadEvent() {
    return JSON.parse(
        fs.readFileSync(
            EVENT_PATH,
            'utf8'
        )
    );
}


function makePayload(
    withCover,
    withLyrics
) {
    const payload = {
        status: 'ok',
        provider: 'navidrome',

        match: {
            id: 'song-1',
            title: 'Bosco',
            artist: 'Placebo',
            album: 'Loud Like Love'
        },

        queue: {
            kind: 'song',
            title: 'Bosco',
            artist: 'Placebo',
            index: 0,
            position: 1,
            count: 1,
            hasNext: false
        },

        stream: {
            url:
                'https://media.example.com/'
                + 'stream.mp3',
            token: 'ndq1.test',
            ttlSeconds: 7200
        }
    };

    if (withCover) {
        payload.match.coverUrl =
            'https://media.example.com/'
            + 'cover.jpg';
    }

    if (withLyrics) {
        payload.stream.captionData = {
            type: 'WEBVTT',
            content:
                'WEBVTT\n\n'
                + '00:00:01.000 --> '
                + '00:00:02.000\n'
                + 'Test\n'
        };
    }

    return payload;
}


function getPlayDirective(response) {
    const directives =
        (
            response
            && response.response
            && response.response.directives
        )
        || [];

    const directive =
        directives.find(
            function (item) {
                return (
                    item.type
                    === 'AudioPlayer.Play'
                );
            }
        );

    if (!directive) {
        throw new Error(
            'AudioPlayer.Play directive missing.'
        );
    }

    return directive;
}


async function runCoverLyricsTest() {
    bridgePayload = makePayload(
        true,
        true
    );

    const response = await handler(
        loadEvent(),
        {}
    );

    const directive =
        getPlayDirective(response);

    const stream =
        directive.audioItem.stream;

    const metadata =
        directive.audioItem.metadata;

    if (
        !stream.captionData
        || stream.captionData.type
            !== 'WEBVTT'
        || stream.captionData.content
            !== bridgePayload
                .stream
                .captionData
                .content
    ) {
        throw new Error(
            'WEBVTT captionData missing '
            + 'or changed.'
        );
    }

    if (
        !metadata.art
        || !metadata.art.sources
        || metadata.art.sources[0].url
            !== bridgePayload.match.coverUrl
    ) {
        throw new Error(
            'Cover artwork missing.'
        );
    }

    if (
        !metadata.backgroundImage
        || !metadata
            .backgroundImage
            .sources
        || metadata
            .backgroundImage
            .sources[0]
            .url
            !== bridgePayload.match.coverUrl
    ) {
        throw new Error(
            'Background artwork missing.'
        );
    }

    console.log(
        'Passed: cover + WEBVTT captionData'
    );
}


async function runFallbackTest() {
    bridgePayload = makePayload(
        false,
        false
    );

    const response = await handler(
        loadEvent(),
        {}
    );

    const directive =
        getPlayDirective(response);

    const stream =
        directive.audioItem.stream;

    const metadata =
        directive.audioItem.metadata;

    if (
        Object.prototype
            .hasOwnProperty.call(
                stream,
                'captionData'
            )
    ) {
        throw new Error(
            'captionData unexpectedly present.'
        );
    }

    if (
        Object.prototype
            .hasOwnProperty.call(
                metadata,
                'art'
            )
        || Object.prototype
            .hasOwnProperty.call(
                metadata,
                'backgroundImage'
            )
    ) {
        throw new Error(
            'Artwork unexpectedly present.'
        );
    }

    console.log(
        'Passed: no-cover/no-lyrics fallback'
    );
}


(async function () {
    await runCoverLyricsTest();
    await runFallbackTest();

    console.log(
        'Lambda media metadata tests passed.'
    );
})().catch(
    function (error) {
        console.error(error);
        process.exit(1);
    }
);
