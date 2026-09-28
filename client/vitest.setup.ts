import "@testing-library/jest-dom";

class ResizeObserverMock implements ResizeObserver {
	constructor(_callback: ResizeObserverCallback) {}

	observe(): void {}

	unobserve(): void {}

	disconnect(): void {}
}

globalThis.ResizeObserver = ResizeObserverMock;
