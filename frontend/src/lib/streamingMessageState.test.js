import assert from 'node:assert/strict';
import { describe, it } from 'node:test';
import {
  appendChunkToBotMessage,
  appendUserAndBotPlaceholder,
  finalizeBotMessage,
} from './streamingMessageState.ts';

describe('streamingMessageState', () => {
  it('adds user + placeholder bot immediately', () => {
    const initial = [];
    const userMessage = { id: 'u1', role: 'user', content: 'Hello' };
    const result = appendUserAndBotPlaceholder(initial, userMessage, 'b1');

    assert.equal(result.length, 2);
    assert.deepEqual(result[0], userMessage);
    assert.deepEqual(result[1], { id: 'b1', role: 'bot', content: '' });
  });

  it('grows bot content progressively as chunks arrive', () => {
    let state = [
      { id: 'u1', role: 'user', content: 'Hello' },
      { id: 'b1', role: 'bot', content: '' },
    ];

    state = appendChunkToBotMessage(state, 'b1', 'Hello ');
    assert.equal(state[1].content, 'Hello ');

    state = appendChunkToBotMessage(state, 'b1', 'world');
    assert.equal(state[1].content, 'Hello world');
  });

  it('final text matches concatenated chunks', () => {
    const beforeFinalize = [
      { id: 'u1', role: 'user', content: 'Hello' },
      { id: 'b1', role: 'bot', content: 'Hello world' },
    ];

    const finalized = finalizeBotMessage(beforeFinalize, 'b1', 'Hello world');
    assert.equal(finalized[1].content, 'Hello world');
  });
});
