# GitHub App credential helper

The image builds [git-credential-github-app](https://github.com/bdellegrazie/git-credential-github-app)
at commit `44092188bcdbbc209317424429489b2335793617`.
The upstream project is licensed under Apache 2.0. This directory retains its
licence. The runtime image also retains the upstream licence and the vendored
dependencies, including their licence files.

Gitea schedules and performs mirror pushes. The helper supplies a fresh GitHub
App installation token through Git's credential protocol. No token-refresh
service or custom push scheduler is added.
