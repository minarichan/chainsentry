import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import { SCAN_CHAINS, type ScanChainId } from "../data/chains";

interface Props {
  id: string;
  value: ScanChainId;
  disabled?: boolean;
  onChange: (chainId: ScanChainId) => void;
}

export function ChainSelect({ id, value, disabled, onChange }: Props) {
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const rootRef = useRef<HTMLDivElement>(null);
  const listId = useId();
  const current = SCAN_CHAINS.find((chain) => chain.id === value) ?? SCAN_CHAINS[0];

  useEffect(() => {
    if (!open) return;
    setActive(SCAN_CHAINS.findIndex((chain) => chain.id === value));

    function onPointer(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) setOpen(false);
    }
    function onKey(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open, value]);

  function pick(chainId: ScanChainId) {
    onChange(chainId);
    setOpen(false);
  }

  function onTriggerKey(event: ReactKeyboardEvent<HTMLButtonElement>) {
    if (event.key === "ArrowDown" || event.key === "Enter" || event.key === " ") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      if (event.key === "Enter" || event.key === " ") {
        const chain = SCAN_CHAINS[active];
        if (chain) pick(chain.id);
      }
      if (event.key === "ArrowDown") {
        setActive((index) => (index + 1) % SCAN_CHAINS.length);
      }
    }
    if (event.key === "ArrowUp") {
      event.preventDefault();
      if (!open) {
        setOpen(true);
        return;
      }
      setActive((index) => (index - 1 + SCAN_CHAINS.length) % SCAN_CHAINS.length);
    }
  }

  return (
    <div className="chain-select" ref={rootRef}>
      <button
        id={id}
        type="button"
        className="chain-select-trigger"
        disabled={disabled}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={listId}
        aria-label="Chain"
        onClick={() => setOpen((next) => !next)}
        onKeyDown={onTriggerKey}
      >
        {current.label}
        <svg className="chain-select-chevron" viewBox="0 0 12 8" aria-hidden="true">
          <path
            d="M1.5 1.75 6 6.25 10.5 1.75"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
        </svg>
      </button>
      {open ? (
        <ul className="chain-select-menu" id={listId} role="listbox" aria-label="Chain">
          {SCAN_CHAINS.map((chain, index) => {
            const selected = chain.id === value;
            return (
              <li key={chain.id} role="none">
                <button
                  type="button"
                  role="option"
                  aria-selected={selected}
                  className={`chain-select-option${selected ? " is-selected" : ""}${index === active ? " is-active" : ""}`}
                  onMouseEnter={() => setActive(index)}
                  onClick={() => pick(chain.id)}
                >
                  {chain.label}
                </button>
              </li>
            );
          })}
        </ul>
      ) : null}
    </div>
  );
}
