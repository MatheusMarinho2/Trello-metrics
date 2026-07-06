import { Fragment, type ReactNode } from "react";

function inlineNodes(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  const pattern = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  let partIndex = 0;

  while ((match = pattern.exec(text)) !== null) {
    if (match.index > lastIndex) {
      nodes.push(text.slice(lastIndex, match.index));
    }
    const token = match[0];
    if (token.startsWith("`")) {
      nodes.push(
        <code key={`${keyPrefix}-code-${partIndex}`} className="ai-code">
          {token.slice(1, -1)}
        </code>,
      );
    } else {
      nodes.push(
        <strong key={`${keyPrefix}-strong-${partIndex}`}>{token.slice(2, -2)}</strong>,
      );
    }
    lastIndex = match.index + token.length;
    partIndex += 1;
  }

  if (lastIndex < text.length) {
    nodes.push(text.slice(lastIndex));
  }
  return nodes.length ? nodes : [text];
}

function isUnfairCallout(lines: string[]): boolean {
  const joined = lines.join(" ").toLowerCase();
  return (
    joined.includes("indevido") ||
    joined.includes("nao faz sentido") ||
    joined.includes("não faz sentido") ||
    joined.includes("id trello") ||
    joined.includes("revisar se deve abater")
  );
}

export function AiMarkdown({ text }: { text: string }) {
  const lines = text.split("\n");
  const blocks: ReactNode[] = [];
  let index = 0;
  let blockIndex = 0;

  const pushBlock = (node: ReactNode) => {
    blocks.push(<Fragment key={`block-${blockIndex}`}>{node}</Fragment>);
    blockIndex += 1;
  };

  while (index < lines.length) {
    const trimmed = lines[index].trim();

    if (!trimmed) {
      pushBlock(<div className="analysis-spacer" />);
      index += 1;
      continue;
    }

    if (trimmed.startsWith(">")) {
      const quoteLines: string[] = [];
      while (index < lines.length && lines[index].trim().startsWith(">")) {
        quoteLines.push(lines[index].trim().replace(/^>\s?/, ""));
        index += 1;
      }
      const unfair = isUnfairCallout(quoteLines);
      pushBlock(
        <blockquote
          className={unfair ? "ai-callout ai-callout-warn" : "ai-callout"}
        >
          {quoteLines.map((line, quoteIndex) => (
            <p key={`quote-${blockIndex}-${quoteIndex}`}>{inlineNodes(line, `q-${blockIndex}-${quoteIndex}`)}</p>
          ))}
        </blockquote>,
      );
      continue;
    }

    if (/^[-*] /.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^[-*] /.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^[-*] /, ""));
        index += 1;
      }
      pushBlock(
        <ul className="ai-list">
          {items.map((item, itemIndex) => (
            <li key={`li-${blockIndex}-${itemIndex}`}>{inlineNodes(item, `li-${blockIndex}-${itemIndex}`)}</li>
          ))}
        </ul>,
      );
      continue;
    }

    if (/^\d+\.\s/.test(trimmed)) {
      const items: string[] = [];
      while (index < lines.length && /^\d+\.\s/.test(lines[index].trim())) {
        items.push(lines[index].trim().replace(/^\d+\.\s/, ""));
        index += 1;
      }
      pushBlock(
        <ol className="ai-list ai-list-ordered">
          {items.map((item, itemIndex) => (
            <li key={`oli-${blockIndex}-${itemIndex}`}>{inlineNodes(item, `oli-${blockIndex}-${itemIndex}`)}</li>
          ))}
        </ol>,
      );
      continue;
    }

    if (trimmed.startsWith("#### ")) {
      pushBlock(<h6 className="ai-h6">{trimmed.slice(5)}</h6>);
    } else if (trimmed.startsWith("### ")) {
      pushBlock(<h5>{trimmed.slice(4)}</h5>);
    } else if (trimmed.startsWith("## ")) {
      const title = trimmed.slice(3);
      const alertClass = /retorno|indevido|atencao|atenção/i.test(title) ? " ai-h4-alert" : "";
      pushBlock(<h4 className={`ai-h4${alertClass}`}>{title}</h4>);
    } else if (trimmed.startsWith("# ")) {
      pushBlock(<h3>{trimmed.slice(2)}</h3>);
    } else if (/^---+$/.test(trimmed)) {
      pushBlock(<hr className="ai-divider" />);
    } else {
      pushBlock(<p>{inlineNodes(trimmed, `p-${blockIndex}`)}</p>);
    }
    index += 1;
  }

  return <div className="analysis-body">{blocks}</div>;
}
