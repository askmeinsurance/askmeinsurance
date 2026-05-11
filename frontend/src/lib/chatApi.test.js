import assert from 'node:assert/strict';
import { afterEach, describe, it, mock } from 'node:test';
import { streamChatMessage, submitFormAnswers } from './chatApi.ts';

function sseResponse(events) {
  const sseBody = events
    .map(({ event, data }) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`)
    .join('');

  return new Response(new TextEncoder().encode(sseBody), {
    status: 200,
    headers: { 'Content-Type': 'text/event-stream' },
  });
}

afterEach(() => {
  mock.restoreAll();
});

describe('streamChatMessage', () => {
  it('reads chunk text from data.text', async () => {
    const onChunkCalls = [];
    mock.method(globalThis, 'fetch', async () =>
      sseResponse([
        { event: 'chunk', data: { text: 'Hello ' } },
        { event: 'chunk', data: { text: 'world' } },
        { event: 'done', data: { reason: 'completed' } },
      ]),
    );

    const result = await streamChatMessage({
      message: 'hi',
      accessToken: 'token',
      onChunk: (chunk) => onChunkCalls.push(chunk),
    });

    assert.equal(result.text, 'Hello world');
    assert.deepEqual(onChunkCalls, ['Hello ', 'world']);
  });

  it('maps form_requested payload directly from data into UI formRequest', async () => {
    const onFormRequestCalls = [];
    mock.method(globalThis, 'fetch', async () =>
      sseResponse([
        { event: 'chunk', data: { text: 'Please fill this form.' } },
        {
          event: 'form_requested',
          data: {
            form_id: 'f1a9f6de-4d4d-42d5-b893-c783f6f32641',
            conversation_id: '8dc8f808-8a66-4d70-bdd7-c2a4d2db5d3f',
            title: 'Insurance Planning Intake',
            description: 'Answer these short questions.',
            submit_label: 'Submit Details',
            pages: [
              {
                id: 'profile',
                title: 'Profile Basics',
                description: 'Tell me who this plan is for.',
                fields: [
                  {
                    id: 'full_name',
                    label: 'Full Name',
                    type: 'text',
                    required: true,
                    placeholder: 'e.g. Alex Tan',
                    options: [],
                  },
                  {
                    id: 'coverage_type',
                    label: 'Coverage Type',
                    type: 'select',
                    options: [
                      { label: 'Term', value: 'term' },
                      { label: 'Whole Life', value: 'whole_life' },
                    ],
                  },
                ],
              },
            ],
          },
        },
      ]),
    );

    const result = await streamChatMessage({
      message: 'help',
      accessToken: 'token',
      onFormRequest: (request) => onFormRequestCalls.push(request),
    });

    assert.deepEqual(result.formRequest, {
      id: 'f1a9f6de-4d4d-42d5-b893-c783f6f32641',
      title: 'Insurance Planning Intake',
      description: 'Answer these short questions.',
      submitLabel: 'Submit Details',
      pages: [
        {
          id: 'profile',
          title: 'Profile Basics',
          description: 'Tell me who this plan is for.',
          fields: [
            {
              id: 'full_name',
              label: 'Full Name',
              type: 'text',
              required: true,
              placeholder: 'e.g. Alex Tan',
              options: [],
            },
            {
              id: 'coverage_type',
              label: 'Coverage Type',
              type: 'select',
              required: undefined,
              placeholder: undefined,
              options: [
                { label: 'Term', value: 'term' },
                { label: 'Whole Life', value: 'whole_life' },
              ],
            },
          ],
        },
      ],
    });
    assert.equal(onFormRequestCalls.length, 1);
    assert.deepEqual(onFormRequestCalls[0], result.formRequest);
  });
});

describe('submitFormAnswers', () => {
  it('submits to /forms/{uuid}/submit path', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async () => new Response(null, { status: 200 }));

    await submitFormAnswers({
      formId: 'f1a9f6de-4d4d-42d5-b893-c783f6f32641',
      answers: { full_name: 'Alex Tan' },
      accessToken: 'token',
    });

    assert.equal(fetchMock.mock.calls.length, 1);
    const [url] = fetchMock.mock.calls[0]?.arguments ?? [];
    assert.equal(url, '/api/v1/forms/f1a9f6de-4d4d-42d5-b893-c783f6f32641/submit');
  });
});
