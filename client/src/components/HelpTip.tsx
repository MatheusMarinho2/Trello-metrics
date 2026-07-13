import { CircleHelp } from "lucide-react";
import { useRef, useState, type CSSProperties } from "react";
import { createPortal } from "react-dom";

import { metricDescription, metricExample, metricFormula } from "../lib/metricDefinitions";

export function HelpTip({ term }: { term: string }) {
  const description = metricDescription(term);
  const formula = metricFormula(term);
  const example = metricExample(term);
  const hasContent = Boolean(description || formula || example);
  const anchorRef = useRef<HTMLSpanElement>(null);
  const [open, setOpen] = useState(false);
  const [style, setStyle] = useState<CSSProperties>({});

  if (!hasContent) return null;

  function updatePosition() {
    const anchor = anchorRef.current;
    if (!anchor) return;

    const rect = anchor.getBoundingClientRect();
    const margin = 8;
    const maxWidth = 320;
    const showBelow = rect.top < 88;

    let top = showBelow ? rect.bottom + margin : rect.top - margin;
    let transform = showBelow ? "translate(-50%, 0)" : "translate(-50%, -100%)";
    let left = rect.left + rect.width / 2;
    left = Math.max(maxWidth / 2 + 12, Math.min(window.innerWidth - maxWidth / 2 - 12, left));

    setStyle({ top, left, transform, maxWidth });
  }

  function show() {
    updatePosition();
    setOpen(true);
  }

  function hide() {
    setOpen(false);
  }

  const aria = [description, formula && `Formula: ${formula}`, example && `Exemplo: ${example}`]
    .filter(Boolean)
    .join(" ");

  return (
    <>
      <span
        ref={anchorRef}
        className="help-tip"
        tabIndex={0}
        aria-label={aria}
        onMouseEnter={show}
        onMouseLeave={hide}
        onFocus={show}
        onBlur={hide}
      >
        <CircleHelp size={14} />
      </span>
      {open
        ? createPortal(
            <span className="help-tip-popover" style={style} role="tooltip">
              {description ? <span className="help-tip-line">{description}</span> : null}
              {formula && formula !== description ? (
                <span className="help-tip-line">
                  <strong>Formula:</strong> {formula}
                </span>
              ) : null}
              {formula && !description ? <span className="help-tip-line">{formula}</span> : null}
              {example ? (
                <span className="help-tip-line help-tip-example">
                  <strong>Exemplo:</strong> {example}
                </span>
              ) : null}
            </span>,
            document.body,
          )
        : null}
    </>
  );
}
