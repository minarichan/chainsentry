import { useState, type FormEvent } from "react";
import { clearEtherscanKey, readEtherscanKey, storeEtherscanKey } from "../data/etherscanKey";

export function SettingsPage() {
  const [key, setKey] = useState(readEtherscanKey);
  const [saved, setSaved] = useState(false);

  function onSave(event: FormEvent) {
    event.preventDefault();
    storeEtherscanKey(key);
    setKey(readEtherscanKey());
    setSaved(true);
  }

  function onClear() {
    clearEtherscanKey();
    setKey("");
    setSaved(true);
  }

  return (
    <>
      <p className="kicker">This browser</p>
      <h1>Settings</h1>
      <p className="lede">
        An Etherscan key stays on this device and is sent only with the next
        scan. It is not saved in the report, not written to the server database,
        and not required for Sourcify-verified contracts.
      </p>
      <form className="panel" onSubmit={onSave}>
        <div className="panel-head">
          <h2>Etherscan API key</h2>
          <span className="muted">{readEtherscanKey() ? "Saved here" : "Not set"}</span>
        </div>
        <label htmlFor="etherscan-api-key">
          API key
          <input
            id="etherscan-api-key"
            type="password"
            className="mono"
            autoComplete="off"
            spellCheck={false}
            value={key}
            onChange={(event) => {
              setKey(event.target.value);
              setSaved(false);
            }}
            placeholder="Optional — this browser only"
          />
        </label>
        <p className="muted" style={{ marginTop: 12 }}>
          Free keys: etherscan.io/apis. Used after Sourcify misses, before Blockscout.
        </p>
        <div className="row" style={{ marginTop: 16 }}>
          <button className="btn" type="submit">
            Save
          </button>
          <button className="btn ghost" type="button" onClick={onClear}>
            Remove
          </button>
          {saved ? <span className="muted">Saved on this device.</span> : null}
        </div>
      </form>
    </>
  );
}
