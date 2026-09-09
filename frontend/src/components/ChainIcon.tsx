import type { ScanChainId } from "../data/chains";

export function ChainIcon({ chainId }: { chainId: ScanChainId }) {
  if (chainId === 1) {
    return (
      <svg className="chain-icon" viewBox="0 0 32 48" aria-hidden="true">
        <path fill="currentColor" d="M16 0 0 24.2 16 33.1 32 24.2z" />
        <path fill="currentColor" opacity="0.72" d="M16 35.6 0 27 16 47.6 32 27z" />
      </svg>
    );
  }
  if (chainId === 8453) {
    return (
      <svg className="chain-icon" viewBox="0 0 32 32" aria-hidden="true">
        <path
          fill="currentColor"
          fillRule="evenodd"
          d="M10 3h12a7 7 0 0 1 7 7v12a7 7 0 0 1-7 7H10a7 7 0 0 1-7-7V10a7 7 0 0 1 7-7zm6 7a6 6 0 1 0 0 12 6 6 0 0 0 0-12z"
        />
      </svg>
    );
  }
  return (
    <svg className="chain-icon" viewBox="0 0 32 32" aria-hidden="true">
      <path
        fill="currentColor"
        d="M16 3 4 28h5.2l2.1-4.6h9.4L22.8 28H28L16 3zm0 9.2 2.7 6H13.3z"
      />
    </svg>
  );
}
