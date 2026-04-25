import { describe, expect, it } from 'vitest';
import { secretaryChatUrl } from '../secretary';

describe('secretaryChatUrl', () => {
  it('returns the bare endpoint when no sessionId is provided', () => {
    expect(secretaryChatUrl()).toBe('/api/departments/secretary/chat');
  });

  it('appends an encoded session_id query parameter when provided', () => {
    expect(secretaryChatUrl('s1')).toBe(
      '/api/departments/secretary/chat?session_id=s1',
    );
    expect(secretaryChatUrl('with spaces & chars')).toBe(
      '/api/departments/secretary/chat?session_id=with%20spaces%20%26%20chars',
    );
  });
});
