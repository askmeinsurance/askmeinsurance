import assert from 'node:assert/strict';
import { afterEach, describe, it, mock } from 'node:test';
import {
  deleteConversation,
  getConversationMessages,
  listConversations,
  streamChatMessage,
  submitFormAnswers,
} from './chatApi.ts';

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
        { event: 'meta', data: { conversation_id: 'f1a9f6de-4d4d-42d5-b893-c783f6f32641' } },
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
    assert.equal(result.conversationId, 'f1a9f6de-4d4d-42d5-b893-c783f6f32641');
    assert.deepEqual(onChunkCalls, ['Hello ', 'world']);
  });

  it('reads chunk text from block-style data.text payload', async () => {
    const onChunkCalls = [];
    mock.method(globalThis, 'fetch', async () =>
      sseResponse([
        { event: 'meta', data: { conversation_id: 'f1a9f6de-4d4d-42d5-b893-c783f6f32641' } },
        {
          event: 'chunk',
          data: { text: [{ type: 'text', text: 'Hello ' }, { type: 'text', text: 'world' }] },
        },
        { event: 'done', data: { reason: 'completed' } },
      ]),
    );

    const result = await streamChatMessage({
      message: 'hi',
      accessToken: 'token',
      onChunk: (chunk) => onChunkCalls.push(chunk),
    });

    assert.equal(result.text, 'Hello \nworld');
    assert.equal(result.conversationId, 'f1a9f6de-4d4d-42d5-b893-c783f6f32641');
    assert.deepEqual(onChunkCalls, ['Hello \nworld']);
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

describe('conversation APIs', () => {
  it('lists conversations', async () => {
    mock.method(globalThis, 'fetch', async () =>
      new Response(
        JSON.stringify([{ id: 'c1', title: 'Life Insurance', created_at: '2026-01-01', updated_at: '2026-01-01' }]),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const result = await listConversations('token');
    assert.equal(result.length, 1);
    assert.equal(result[0].title, 'Life Insurance');
  });

  it('gets conversation messages', async () => {
    mock.method(globalThis, 'fetch', async () =>
      new Response(
        JSON.stringify([{ id: 'm1', conversation_id: 'f1a9f6de-4d4d-42d5-b893-c783f6f32641', role: 'user', content: 'hi' }]),
        { status: 200, headers: { 'Content-Type': 'application/json' } },
      ),
    );
    const result = await getConversationMessages('f1a9f6de-4d4d-42d5-b893-c783f6f32641', 'token');
    assert.equal(result.length, 1);
    assert.equal(result[0].role, 'user');
  });

  it('deletes a conversation', async () => {
    const fetchMock = mock.method(globalThis, 'fetch', async () => new Response(null, { status: 204 }));
    await deleteConversation('f1a9f6de-4d4d-42d5-b893-c783f6f32641', 'token');
    assert.equal(fetchMock.mock.calls.length, 1);
    const [url, options] = fetchMock.mock.calls[0]?.arguments ?? [];
    assert.equal(url, '/api/v1/conversations/f1a9f6de-4d4d-42d5-b893-c783f6f32641');
    assert.equal(options.method, 'DELETE');
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
