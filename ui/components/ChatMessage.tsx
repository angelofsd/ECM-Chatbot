"use client";

import React, { useState } from "react";
import { Citation } from "@/lib/api";
import { ChevronDown, ChevronUp } from "lucide-react";

interface ChatMessageProps {
  message: {
    id: string;
    role: "user" | "assistant";
    content: string;
    citations?: Citation[];
    timestamp: Date;
  };
}

export default function ChatMessage({ message }: ChatMessageProps) {
  const [expandedCitations, setExpandedCitations] = useState(false);
  const isUser = message.role === "user";

  return (
    <div
      className={`flex ${isUser ? "justify-end" : "justify-start"} animate-fade-in`}
    >
      <div
        className={`max-w-2xl rounded-lg px-4 py-3 ${
          isUser
            ? "bg-primary text-primary-foreground rounded-br-none"
            : "bg-muted text-muted-foreground rounded-bl-none"
        }`}
      >
        {/* Message content */}
        <div className={`text-sm leading-relaxed whitespace-pre-wrap`}>
          {message.content}
        </div>

        {/* Citations (only for assistant) */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-current border-opacity-20">
            <button
              onClick={() => setExpandedCitations(!expandedCitations)}
              className="flex items-center gap-2 text-xs font-semibold hover:opacity-80 transition-opacity"
            >
              {expandedCitations ? (
                <ChevronUp size={14} />
              ) : (
                <ChevronDown size={14} />
              )}
              Sources ({message.citations.length})
            </button>

            {expandedCitations && (
              <div className="mt-2 space-y-2">
                {message.citations.map((citation, idx) => (
                  <div
                    key={`${citation.filename}-${idx}`}
                    className="text-xs bg-current bg-opacity-10 rounded p-2"
                  >
                    <p className="font-semibold truncate">
                      {citation.filename}
                    </p>
                    <p className="text-opacity-70">
                      Referenced {citation.citation_count} time
                      {citation.citation_count !== 1 ? "s" : ""}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Timestamp */}
        <div
          className={`text-xs mt-2 opacity-60 ${
            isUser ? "text-right" : "text-left"
          }`}
        >
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
