// A matchMedia for jsdom, where every query matches or none does.
export function mediaQueries(matches: boolean): typeof window.matchMedia {
  return (query) =>
    ({
      matches,
      media: query,
      onchange: null,
      addEventListener: () => undefined,
      removeEventListener: () => undefined,
      addListener: () => undefined,
      removeListener: () => undefined,
      dispatchEvent: () => false,
    }) satisfies MediaQueryList
}
