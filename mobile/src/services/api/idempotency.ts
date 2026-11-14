export function newKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  // The key correlates retries. It is neither a credential nor a security token.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const nibble = Math.floor(Math.random() * 16);
    return (character === 'x' ? nibble : (nibble & 3) | 8).toString(16);
  });
}
