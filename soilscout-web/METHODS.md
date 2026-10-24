# SoilScout Carbon Planner

A separate hackathon prototype for Bhoomika's soil-carbon extension. This project does not modify or call Parnita-C/UCD_UN_RebootTheEarth_2026.

## Implemented

- Click/drag a map pin or enter coordinates; read actual supplied organic-matter and baseline carbon raster cells.
- Preserve no-data and out-of-extent results. Default example is farmland near Davis at 38.53, -121.8.
- Compare cover crops, reduced/no tillage, and compost with 2,204 COMET-Planner v4.0 Build 2 records across all 58 California counties. County is manually selected; changing the pin clears it except for the named examples.
- Compute 1-, 3-, and 5-year screening extrapolations, distinct soil carbon and total GHG benefits, cohort-vested conditional cash, costs and savings. Export source row, version, hash, assumptions and results as JSON.
- A source-based rule helper answers questions using the selected pin and financial scenario. **No live generative AI model is connected.** It does not infer available nitrogen.

## Files to work on

- `app/page.tsx`: farmer-facing screens and state.
- `components/soil-map.tsx`: Leaflet map and marker interactions.
- `lib/soil-model.mjs`: sampling and advisory functions.
- `components/carbon-planner.tsx`: county/practice controls, published evidence and results.
- `lib/regional-model.mjs`: carbon and financial calculations.
- `public/data/comet-ca.json`: source records and provenance.
- `scripts/soil/extract_comet.py`: memory-bounded XLSX extraction using the Python standard library; maps cell addresses to preserve omitted blank cells.
- `public/data/metadata.json`: grid geometry, provenance hashes, units, and caveats.
- `public/data/*.f32`: little-endian Float32 grids; NaN means no data.
- `scripts/soil/prepare_data.py`: reproducible GeoTIFF conversion; requires numpy, rasterio, and Pillow. Run `python scripts/soil/prepare_data.py --input-dir /path/to/original-tifs`.
- `scripts/soil/validate.mjs`: meaningful numeric and source-data checks.

## Run/check

Install dependencies with pnpm, then use `pnpm dev` or the Sites preview workflow. Run `node scripts/soil/validate.mjs` and `pnpm exec tsc --noEmit`. The Sites build uses `pnpm build` through its configured build helper.

## Scientific boundaries

Organic matter is kg/m² total-profile stock, not a percentage. The supplied file does not encode its precise depth or observation year. Carbon is interpreted using FAO GSOCseq documentation as t C/ha, 0–30 cm, T0 model reference 2020; the file itself has no unit tags. Organic matter is reprojected from EPSG:5070 to the baseline's EPSG:4326 grid using nearest-neighbor resampling. These are grid estimates, not current field tests.

COMET-Planner v4.0 Build 2, updated October 22, 2025, downloaded October 24, 2026, replaces the global default. Source: https://storage.googleapis.com/comet-pln-dom-pub/US_COMETPlanner_data.xlsx . Source workbook hash is in the bundled subset. Extract with `python scripts/soil/extract_comet.py /path/to/US_COMETPlanner_data.xlsx`. Attribution: Swan, Locatelli, Toureene, Easter, Chambers, Brown, Williams, Creque, Wick and Paustian (2025), COMET-Planner Dataset v4.0 Build 2. Methods: https://comet-planner.com/api/resource/pdf/COMET-Planner_Report.pdf .

Use the source `soil_carbon_co2` column for soil carbon, converted from t CO2e/acre/year by 12/44. Use `total_ghg_co2` for net modeled GHG benefits. Negative values remain negative; -999 becomes null. We do not use source min/max columns as confidence intervals. The source models 10-year scenarios and averages across county-rectified MLRAs (or LRR fallbacks). Multiplication by 1, 3 or 5 is a constant-rate screening extrapolation, not a time-resolved forecast. Common annual row crops on mineral soils are the screening scope. Most specialty crops, orchard/vineyards, organic soils and flooded rice require other evidence. The independent GSOCseq baseline is not added to these results.

Cover-crop operating costs default to the UC Davis/UCCE Lower Sacramento Valley 2022 budget, $156/acre/year (plant69 + irrigation44 + mowing21 + disc22). Land, management and overhead are excluded; no inflation adjustment is made. This budget is an explicitly labeled comparison, not a matched budget for every modeled scenario. Potential fertilizer savings of $36/acre (30 lb available N at $1.20/lb) are documented but default to zero. Source: https://coststudyfiles.ucdavis.edu/uploads/pub/2022/09/28/2022covercropsbenefits.pdf . Other practices and changed counties clear costs rather than assuming zero. Intermittent compost costs entered by the user are annualized planning costs, not cash expenditure schedules.

Payments use Indigo's historical $30 per sold credit paid to farmers for 2020–2021 carbon crops, announced August 2022. This already incorporates the farmer share: do not deduct 25% again. Historical example includes a 20% buffer and five-year vesting fractions 50/20/10/10/10. Each annual credit cohort vests independently after an explicitly assumed one-year sale delay. All rates are editable. Historical payment source: https://www.indigoag.com/blog/announcing-indigo-carbon-payment-rate-for-the-2020-and-2021-crops . Vesting source: https://app.indigoag.com/programs/learn/paper/why-does-it-take-time-to-repair-soil-to-store-carbon . These are not current quotes, actual credits, or an eligibility determination. Existing adoption pauses payments. Compost payments are withheld because imported carbon requires lifecycle and program-specific eligibility accounting. No corporate buyer, registry, live price feed or enrollment is connected. Yield effects, crop premiums, grants and unentered expenses are excluded. Partial net cash is not whole-farm profitability.

Default 100-acre Yolo legume/intensive-till/irrigated/no-N-reduction record: source row43213, soil-carbon CO2 .462243799591439 t/acre/year; totalGHG .403777459969602. Five-year extrapolation:63.0332454 tC and201.88872998 tCO2e totalGHG; conditional vested cash$2,810.29, operating costs$78,000, zero assumed savings. Scientific and economics tests verify source-column mapping, GHG reconciliation, missing/negative values, carbon conversion, payment cohorts and eligibility gates.

## Integrated crop engine

Parnita’s original repository is unchanged. SoilScout includes a browser-compatible port of `evaluate_next_crops` from commit `fbba4b8efa4537ac66333aada3ffc0308db8f162`, original Python sources in `vendor/parnita/`, and her four actual Central Valley soil maps in `public/data/crops/`. No separate Python server is needed. This is a pinned integration, not automatic synchronization with future upstream changes.

- `lib/crop-model.mjs`: unchanged rule weights and stable tie order; native CRS sampling with proj4. Added explicit coverage bounds and safe missing-layer handling. Display wording corrects the original unsupported nitrogen/disease diagnoses without changing scores.
- `lib/crop-catalog.json`: extracted from original Python constants.
- `components/crop-planner.tsx`: shared field, previous three crops, all seven rankings and downloadable evidence.
- Advisor reads the same profile, history and computed results. Carbon scenarios retain their independent county/system selection. Rankings do not imply carbon payments.
- `scripts/soil/prepare_crop_data.py SOURCE_DIR`: reproducibly converts the original GeoTIFFs without resampling (numpy and rasterio required). Metadata retains source URLs, commit, hashes, grid geometry and units. GeoTIFF no-data becomes NaN.
- `python scripts/soil/crop_parity.py` checks the JS scoring port against the original Python function across every three-crop history and varied pH, EC and textures. `node scripts/soil/validate-crops.mjs` checks coverage, missing data and advisor integration.

The advisor remains a source-based rule helper, not a live generative AI model. Crop scores are heuristics, not validated agronomic predictions. Unknown history is ignored by the original rules and visibly flagged. Weather, available nitrogen and planting calendars are not measured. Crop and map state persists across screens for the current visit; moving the pin clears crop history to avoid applying another field’s rotation; there is no account database for saved farm records.

Sources are linked in the Evidence & Methods screen. The app does not store or transmit user queries to an AI provider. Base-map imagery tiles are fetched from Esri World Imagery and receive ordinary map tile requests.
