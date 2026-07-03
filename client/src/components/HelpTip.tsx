import { CircleHelp } from "lucide-react";

import { metricDescription } from "../lib/metricDefinitions";

export function HelpTip({ term }: { term: string }) {
  const text = metricDescription(term);
  if (!text) return null;

  return (
    <span className="help-tip" tabIndex={0} aria-label={text} data-tooltip={text}>
      <CircleHelp size={14} />
    </span>
  );
}
