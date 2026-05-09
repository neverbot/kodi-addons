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

The GitHub Action runs on three triggers:

- `push` to `master` (so editing `build.py`, `addons.json` or the
  `repository.neverbot/` source republishes immediately).
- `workflow_dispatch` (manual button from the Actions tab).
- `repository_dispatch` of type `addon-released` — fired by tracked
  add-on repos when they push a release tag (see below).

### Releasing a new version of an add-on

1. In the add-on repo, bump `version` in `addon.xml`, commit and push:
   ```sh
   git commit -am "release v0.2.0"
   git tag v0.2.0
   git push --tags
   ```
2. The add-on repo's `notify-kodi-addons.yml` workflow fires on the tag
   push, sends a `repository_dispatch` to this repo, and the publish
   workflow rebuilds `docs/` automatically. End users see the update on
   Kodi's next add-on check (~1 h).

### Setting up a tracked add-on repo for automatic publish

Each tracked add-on needs a workflow that pings this repo on tag push.
Copy [`notify-kodi-addons.yml`](https://github.com/neverbot/plugin.video.cinematic.collections/blob/master/.github/workflows/notify-kodi-addons.yml)
into `.github/workflows/` of the add-on repo, then create a
**fine-grained Personal Access Token** with the following scope:

- *Repository access* → only `neverbot/kodi-addons`.
- *Repository permissions* → **Contents: read**, **Metadata: read** and
  the all-important **Actions: read and write** (lets the token fire the
  dispatch event).

Store the token as the secret `KODI_REPO_DISPATCH_TOKEN` in the add-on
repo (Settings → Secrets and variables → Actions → New repository
secret).

### Adding a new add-on to the repo

1. Append an entry to `addons.json` with `id` and `github`.
2. Push. The publish workflow will pull it on its next run.

### Building locally

```sh
python3 build.py
git add docs/ && git commit -m "publish: …" && git push
```
