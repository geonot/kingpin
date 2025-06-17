// Basic test to verify Jest is working
describe('Test Setup', () => {
  test('Jest is working correctly', () => {
    expect(true).toBe(true);
  });

  test('can perform basic arithmetic', () => {
    expect(2 + 2).toBe(4);
  });

  test('can use async/await', async () => {
    const promise = Promise.resolve('hello');
    const result = await promise;
    expect(result).toBe('hello');
  });
});
