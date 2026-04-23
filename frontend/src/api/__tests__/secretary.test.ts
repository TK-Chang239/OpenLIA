import { describe, it, expect } from 'vitest';
import { secretaryChatUrl } from '../secretary';

describe('secretaryChatUrl', () => {
  it('returns the chat route with no session id', () => {
    expect(secretaryChatUrl()).toBe('/api/departments/secretary/chat');
  });
  it('appends session id as a query parameter', () => {
    expect(secretaryChatUrl('abc-123')).toBe(
      '/api/departments/secretary/chat?session_id=abc-123',
    );
  });
});
