
import { evaluateNextCrops } from './crop-model.mjs';

export type FarmGoal = 'crops' | 'carbon' | 'both';

export type FarmInput = {
  location: {
    lat: number;
    lon: number;
    label: string;
  };
  acres: number;
  history: string[];
  cropProfile: any;
  carbonProjection: any;
};

export type FarmAssistantResult = {
  goal: FarmGoal;
  cropRecommendations?: any;
  carbonSequestration?: any;
};

export function runFarmAssistant(
  goal: FarmGoal,
  farm: FarmInput,
): FarmAssistantResult {
  if (
    !Number.isFinite(farm.location.lat) ||
    Math.abs(farm.location.lat) > 90 ||
    !Number.isFinite(farm.location.lon) ||
    Math.abs(farm.location.lon) > 180
  ) {
    throw new Error('Please provide a valid farm location.');
  }

  if (!Number.isFinite(farm.acres) || farm.acres <= 0) {
    throw new Error('Please enter a valid field area.');
  }

  if (
    farm.history.length !== 3 ||
    farm.history.some((crop) => !crop.trim())
  ) {
    throw new Error(
      'Please enter the last three crop cycles, oldest first.',
    );
  }

  const result: FarmAssistantResult = { goal };

  if (goal === 'crops' || goal === 'both') {
    if (!farm.cropProfile?.in_central_valley) {
      result.cropRecommendations = {
        available: false,
        reason:
          'The crop recommender does not cover this location. No recommendations were generated.',
      };
    } else {
      const ranked = evaluateNextCrops(
        farm.history,
        farm.cropProfile,
      );

      result.cropRecommendations = {
        available: true,
        items: ranked.filter(
          (item: any) =>
            typeof item.crop === 'string' &&
            Number.isFinite(item.score),
        ),
        note:
          'Scores are heuristic rotation-ranking points, not probabilities or yield forecasts.',
      };
    }
  }

  if (goal === 'carbon' || goal === 'both') {
    const projection = farm.carbonProjection;

    if (
      projection?.rows &&
      Array.isArray(projection.rows) &&
      projection.rows.length > 0
    ) {
      result.carbonSequestration = {
        available: true,
        county: projection.county ?? null,
        practiceID: projection.practiceID ?? null,
        implementation: projection.implementation ?? null,
        rows: projection.rows,
        note:
          'Regional modeled scenario, not a field measurement, verified credit, or guaranteed payment.',
      };
    } else {
      result.carbonSequestration = {
        available: false,
        reason:
          'No carbon projection is ready. Open the Carbon Planner, select a supported county and practice, and review the scenario inputs first.',
      };
    }
  }

  return result;
}
