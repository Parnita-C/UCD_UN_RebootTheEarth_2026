'use client';

import { useState } from 'react';
import { ArrowRight, Leaf, Sprout, Layers } from 'lucide-react';
import {
  runFarmAssistant,
  type FarmGoal,
} from '../lib/farm-assistant';

type Props = {
  location: {
    lat: number;
    lon: number;
    label: string;
  };
  acres: string;
  history: string[];
  setHistory: (history: string[]) => void;
  cropProfile: any;
  carbonProjection: any;
  onOpenCarbonPlanner: () => void;
};

type ChatMessage = {
  role: 'assistant' | 'user';
  text: string;
};

export default function FarmChat({
  location,
  acres,
  history,
  setHistory,
  cropProfile,
  carbonProjection,
  onOpenCarbonPlanner,
}: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: 'assistant',
      text:
        'Welcome to SoilScout. I can help you explore crop recommendations and carbon scenarios using your farm data. First, confirm your location, field area, and the last three crop cycles.',
    },
  ]);

  function runGoal(goal: FarmGoal) {
    setMessages((previous) => [
      ...previous,
      {
        role: 'user',
        text:
          goal === 'crops'
            ? 'Recommend my next crop'
            : goal === 'carbon'
              ? 'Estimate carbon sequestration'
              : 'Explore both options',
      },
    ]);

    try {
      const result = runFarmAssistant(goal, {
        location,
        acres: Number(acres),
        history,
        cropProfile,
        carbonProjection,
      });

      const sections: string[] = [];

      if (result.cropRecommendations) {
        const cropResult = result.cropRecommendations;

        if (!cropResult.available) {
          sections.push(
            `Crop recommendations unavailable: ${cropResult.reason}`,
          );
        } else {
          const items = cropResult.items as Array<{
            crop: string;
            score: number;
            reasons: string[];
          }>;

          sections.push(
            'Crop recommendations\n' +
              items
                .slice(0, 5)
                .map(
                  (item, index) =>
                    `${index + 1}. ${item.crop} — score ${item.score}/100` +
                    (item.reasons?.length
                      ? `\n   ${item.reasons.join(' ')}`
                      : ''),
                )
                .join('\n') +
              `\n\n${cropResult.note}`,
          );
        }
      }

      if (result.carbonSequestration) {
        const carbon = result.carbonSequestration;

        if (!carbon.available) {
          sections.push(
            `Carbon scenario unavailable: ${carbon.reason}`,
          );
        } else {
          const fiveYear = carbon.rows.find(
            (row: any) => row.year === 5,
          );

          sections.push(
            'Carbon scenario\n' +
              `County: ${carbon.county ?? 'Not specified'}\n` +
              `Practice: ${carbon.implementation ?? carbon.practiceID ?? 'Not specified'}\n` +
              (fiveYear
                ? `Five-year modeled additional soil carbon: ${fiveYear.carbon} t C\n` +
                  `Five-year total GHG reduction: ${fiveYear.ghg} t CO₂e\n` +
                  `Conditional cash: ${fiveYear.cashReceived == null ? '—' : `$${Math.round(fiveYear.cashReceived).toLocaleString()}`}\n` +
                  `Partial net cash: ${fiveYear.net == null ? '—' : `$${Math.round(fiveYear.net).toLocaleString()}`}`
                : 'No five-year result is available.') +
              `\n\n${carbon.note}`,
          );
        }
      }

      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          text: sections.join('\n\n'),
        },
      ]);
    } catch (error) {
      setMessages((previous) => [
        ...previous,
        {
          role: 'assistant',
          text:
            error instanceof Error
              ? error.message
              : 'The request could not be processed.',
        },
      ]);
    }
  }

  return (
    <section className="card chat-card">
      <div className="card-header">
        <div>
          <h2>SoilScout farm assistant</h2>
          <p>Crop planning and carbon scenario exploration</p>
        </div>
      </div>

      <div className="advisor-context">
        <h3>{location.label}</h3>
        <p>
          {acres || '—'} acres · Confirm your crop history
        </p>

        {history.map((crop, index) => (
          <label className="field-input" key={index}>
            {
              [
                'Cycle 1 · Oldest',
                'Cycle 2',
                'Cycle 3 · Most recent',
              ][index]
            }
            <input
              value={crop}
              placeholder="Enter crop"
              onChange={(event) => {
                setHistory(
                  history.map((item, i) =>
                    i === index ? event.target.value : item,
                  ),
                );
              }}
            />
          </label>
        ))}
      </div>

      <div className="chat-messages" aria-live="polite">
        {messages.map((message, index) => (
          <div
            className={`message ${message.role}`}
            key={index}
          >
            {message.role === 'assistant' && (
              <span className="message-icon">
                <Leaf size={16} />
              </span>
            )}
            <div className="message-body">
              <pre className="farm-chat-result">
                {message.text}
              </pre>
            </div>
          </div>
        ))}
      </div>

      <div className="suggestions">
        <button
          disabled={
            !history.every((crop) => crop.trim()) ||
            !cropProfile?.in_central_valley
          }
          onClick={() => runGoal('crops')}
        >
          <Sprout size={16} />
          Recommend next crop
          <ArrowRight size={15} />
        </button>

        <button onClick={onOpenCarbonPlanner}>
          <Leaf size={16} />
          Configure carbon scenario
          <ArrowRight size={15} />
        </button>

        <button
          disabled={!history.every((crop) => crop.trim())}
          onClick={() => runGoal('both')}
        >
          <Layers size={16} />
          Explore both options
          <ArrowRight size={15} />
        </button>
      </div>

      <p className="chat-footer">
        Recommendations use the existing crop model. Carbon results
        use the existing regional scenario projection. Scores are
        heuristic and payments are conditional, not guaranteed.
      </p>
    </section>
  );
}
