# neverbot's Kodi add-on repository

This repo publishes a small Kodi add-on repository so end users can install
add-ons published by [neverbot](https://github.com/neverbot) and receive
updates automatically — the same way they'd consume any third-party Kodi
repo (TMDb Helper, Embuary, …).

The published index is served by GitHub Pages from
[`docs/`](./docs):

- Index: <https://neverbot.github.io/kodi-addons/addons.xml>
- Repository add-on (zip): <https://neverbot.github.io/kodi-addons/repository.neverbot/repository.neverbot-1.0.0.zip>

## For end users

Install once, get every neverbot Kodi add-on (and updates) automatically:

1. Download the [repository add-on
   zip](https://neverbot.github.io/kodi-addons/repository.neverbot/repository.neverbot-1.0.0.zip).
2. In Kodi: **Settings → Add-ons → Install from zip file** → pick the file.
   (You may need to enable "Unknown sources" first.)
3. **Settings → Add-ons → Install from repository → neverbot's Kodi
   add-ons** → browse the available add-ons and install whichever you want.

From now on Kodi will pull updates from this repository on its normal
schedule (about once an hour).

## Add-ons currently published

- [`plugin.video.cinematic.collections`](https://github.com/neverbot/plugin.video.cinematic.collections)
  — custom collections mixing movies and TV shows.

## How this repo works (for me, future me)

```
kodi-addons/
├── repository.neverbot/        # Source of the small repository add-on.
├── addons.json                 # List of external add-ons to track.
├── build.py                    # Builds the published index into docs/.
├── docs/                       # GitHub Pages serves this verbatim.
│   ├── addons.xml
│   ├── addons.xml.md5
│   ├── repository.neverbot/
│   │   └── repository.neverbot-1.0.0.zip
│   └── plugin.video.cinematic.collections/
│       └── plugin.video.cinematic.collections-0.1.0.zip
└── .github/workflows/publish.yml   # Runs build.py and commits docs/.
```

`build.py` reads `addons.json`, fetches the latest GitHub release tag of
each tracked add-on, downloads its source tarball at that tag, packages
it as a Kodi-style zip, and rebuilds `addons.xml` + `addons.xml.md5`. It
also packages the local `repository.neverbot/` source.

The GitHub Action runs daily, on push to `master`, and on manual trigger.
A new tag in any tracked add-on gets picked up by the next scheduled run
(or by hitting "Run workflow" from the Actions tab for an immediate
publish).

### Releasing a new version of an add-on

1. In the add-on repo, bump `version` in `addon.xml`, commit and tag:
   ```sh
   git commit -am "release v0.2.0"
   git tag v0.2.0
   git push --tags
   ```
2. (Optionally) trigger the publish workflow in this repo manually for an
   immediate publish — otherwise wait up to ~24h.

### Adding a new add-on to the repo

1. Append an entry to `addons.json` with `id` and `github`.
2. Push. The publish workflow will pull it on its next run.

### Building locally

```sh
python3 build.py
git add docs/ && git commit -m "publish: …" && git push
```
