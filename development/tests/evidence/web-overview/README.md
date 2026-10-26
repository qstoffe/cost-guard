# Overview browser evidence — FR 000450

2026-10-27, Windows / installed Microsoft Edge headless, synthetic canonical DTOs only.
The four PNGs show baseline `be6c8511b26a71030628fe0d7e8202961ad2582e` at left and this delivery's renderer at right, in 1440px / 360px frames and light / dark themes. All four images were opened and examined: readable metric/account groups, visible amber warnings, wrapped narrow cards and table-local horizontal scrolling. This is agent visual inspection, not owner, physical-device or assistive-technology approval.

Generation reused `development/tests/integration/render_web_design.py --baseline be6c8511b26a71030628fe0d7e8202961ad2582e --output <owned-output>` and `synthetic_reports()`. The historical generator's FR 000440 / navigation captions remain in these images; the actual baseline and change here are FR 000450. The generated gallery iframe height was expanded to 3100px for full-page inspection. Edge used an isolated disposable profile, file access, reduced motion, a 2000ms virtual-time budget and 3100×3550 / 1600×3550 capture windows. No real history, provider credentials or browser sign-in was used. Comparison-table contents are checked by deterministic CLI/DOM tests, not by the old gallery's tableParity flag (Overview deliberately replaces its duplicate quota table with cards).

Reviewed SHA-256:

| Image | SHA-256 |
| --- | --- |
| overview-full-dark-1440px.png | 3aedd9dab53d322e50c32c3cadbd62b04df958ebc0c1ddc7879fd054bbddb0f4 |
| overview-full-dark-360px.png | 9dff5fdde97ca058c60d45aa9536828883d7ab558d692681dc716575c964323a |
| overview-full-light-1440px.png | 7d5428a6a8a5a9789302df9fc6904cafda644f21c9110464cea3454ef4dc8d7c |
| overview-full-light-360px.png | 2458e7160e6fcd7944565e8e33c781f7ac20bae2d48320b437b5af8d7fc9af2d |
