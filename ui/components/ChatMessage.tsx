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
        className={`max-w-[85%] rounded-2xl px-4 py-3 transition-shadow ${
          isUser
            ? "bg-blue-800 text-white rounded-br-none shadow-md"
            : "bg-gray-100 dark:bg-gray-800 text-gray-900 dark:text-gray-100 rounded-bl-none shadow-sm border-l-4 border-indigo-400 pl-3"
        }`}
      >
        {/* Message content */}
        <div className={`text-sm leading-relaxed whitespace-pre-wrap ${!isUser ? "font-semibold text-gray-700 dark:text-gray-200" : ""}`}>
          {message.content}
        </div>

        {/* Citations (only for assistant) */}
        {!isUser && message.citations && message.citations.length > 0 && (
          <div className="mt-3 pt-3 border-t border-gray-300 dark:border-gray-600">
            <button
              onClick={() => setExpandedCitations(!expandedCitations)}
              className="flex items-center gap-2 text-xs font-semibold text-gray-900 dark:text-gray-100 hover:text-blue-600 dark:hover:text-blue-400 transition-colors"
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
                    className="text-xs bg-indigo-50 dark:bg-indigo-900/20 rounded-lg p-3 border border-indigo-200 dark:border-indigo-800"
                  >
                    <p className="font-semibold truncate text-gray-900 dark:text-gray-100">
                      {citation.filename}
                    </p>
                    <p className="text-gray-500 dark:text-gray-400 italic mt-1">
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
          className={`text-xs mt-2 ${
            isUser ? "text-blue-200 text-right" : "text-gray-400 text-left"
          }`}
        >
          {message.timestamp.toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
}
