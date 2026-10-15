import { test as base, expect } from '@playwright/test';
import { user } from './helpers';

// Call FastAPI directly: frontend /documents/* paths are guarded reader pages.
const test = base.extend({
  backend: async ({ playwright }, use) => {
    const backend = await playwright.request.newContext({ baseURL: 'http://127.0.0.1:18001' });
    try {
      await use(backend);
    } finally {
      await backend.dispose();
    }
  },
});
const otherUser = { email: 'other@example.com', password: user.password };

async function bearer(backend, credentials) {
  const response = await backend.post('/auth/login', {
    form: { username: credentials.email, password: credentials.password },
  });
  expect(response.status()).toBe(200);
  const { access_token, token_type } = await response.json();
  expect(token_type).toBe('bearer');
  expect(access_token).toEqual(expect.any(String));
  // Suppress login cookies so subsequent requests prove Bearer authentication.
  return { Authorization: `Bearer ${access_token}`, Cookie: '' };
}

async function documents(backend, headers) {
  const response = await backend.get('/documents', { headers });
  expect(response.status()).toBe(200);
  return response.json();
}

test('guest cannot read document list or detail from the backend', async ({ backend }) => {
  for (const path of ['/documents', '/documents/1']) {
    const response = await backend.get(path);
    expect(response.status()).toBe(401);
    expect(response.headers()['www-authenticate']).toBe('Bearer');
  }
});

test('owner can read their document using a real Bearer token', async ({ backend }) => {
  const headers = await bearer(backend, user);
  const [document] = await documents(backend, headers);
  expect(document.original_filename).toBe('private-playwright_user.pdf');
  const response = await backend.get(`/documents/${document.id}`, { headers });
  expect(response.status()).toBe(200);
  expect(await response.json()).toMatchObject({
    id: document.id, owner_id: document.owner_id, original_filename: document.original_filename,
  });
  expect(await response.json()).not.toHaveProperty('extracted_text');
});

for (const [owner, visitor] of [[user, otherUser], [otherUser, user]]) {
  test(`${visitor.email} is denied the other account's document without leaks or retention changes`, async ({ backend }) => {
    const ownerHeaders = await bearer(backend, owner);
    const visitorHeaders = await bearer(backend, visitor);
    const owned = await documents(backend, ownerHeaders);
    expect(owned).toHaveLength(1);
    const [document] = owned;
    const visible = await documents(backend, visitorHeaders);
    expect(visible).toHaveLength(1);
    expect(visible[0].owner_id).not.toBe(document.owner_id);
    expect(visible.map(item => item.id)).not.toContain(document.id);

    const response = await backend.get(`/documents/${document.id}`, { headers: visitorHeaders });
    expect(response.status()).toBe(403);
    // Exact generic error excludes all document metadata, paths and extracted text.
    expect(await response.json()).toEqual({ detail: 'Access denied' });
    const [after] = await documents(backend, ownerHeaders);
    expect(after.last_accessed_at).toBe(document.last_accessed_at);
    expect(after.expires_at).toBe(document.expires_at);
  });
}

test('missing document still returns 404 for an authenticated user', async ({ backend }) => {
  const headers = await bearer(backend, user);
  const response = await backend.get('/documents/999999', { headers });
  expect(response.status()).toBe(404);
});
