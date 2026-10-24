# SoilScout — standalone website

This copy runs without ChatGPT hosting, authentication, or connectors. It includes the integrated soil maps, seven-crop recommender, carbon scenarios and rule-based advisor.

## Run locally
Install Node.js 22.13 or newer, open a terminal in this folder, then run:

```
npm install
npm run dev
```

Open the URL printed by Vite. Run `npm run build` for production and `npm run preview` to inspect it. Do not open index.html directly from disk: soil-grid loading requires HTTP.

## Deploy to Vercel
Put this folder's contents in a repository you own and import that repository in Vercel. The included vercel.json selects Vite, the build command and dist output. No API keys or environment variables are required. Check the host's access settings before sharing with friends. No custom domain is required.

## Deploy without building
The separate soilscout-ready-to-upload.zip contains the compiled website with all soil maps. Extract it and upload the folder containing index.html to https://app.netlify.com/drop . Sign in to retain control of the deployment and check its visibility settings before sharing. The upload archive is deployable output, not editable source.

## Demo and validation
Use latitude 38.5300, longitude -121.8000. Open Crop planner and choose Use example rotation. These crops are examples, not actual farm history. Moving the pin resets crop history. The crop engine uses the supplied Central Valley maps only.

Run `npm test` for data and calculation checks. Run `python scripts/soil/crop_parity.py` for 2,744 comparisons against Parnita's original Python rules (standard library only). METHODS.md documents provenance and limitations.

No live generative AI, buyer enrollment or registry is connected. Soil values are map estimates. Payments are conditional scenarios. The package contains no ChatGPT chats, account credentials or session history. Esri supplies base-map tiles as in the original app.
