# Sources and licenses

- KDE documentation and manpages: used as *targets to cite* (paths/names). Quoted snippets in the synthetic corpus are short and attributed to local `man(1)` paths.
- Arch Wiki / CachyOS docs: [CC BY-SA](https://wiki.archlinux.org/title/ArchWiki:Copyrights). This corpus does not copy wiki pages verbatim; CachyOS slices are original instruction-tuning paraphrases about pacman/kernel/NVIDIA workflows.
- Sysadmin and network slices: original paraphrases that cite local `man(1)` paths (`ip`, `ss`, `nft`, `resolvectl`, `NetworkManager`, `systemd.*`). The agent is not trained to emit unrestricted `sh -c` for those tools.
- Tool-call general: original templates inspired by public tool-calling sets (xlam-style single-tool turns remapped to kde-ai names). If you remap Salesforce xLAM, follow that dataset's license when mixing the original files; this repo's `data/out` rows are generated templates, not a copy of xLAM.
- Bugzilla / invent: **synthetic** ids and summaries. Do not scrape Discuss or user PII.
- Qwen2.5 weights: remain under the Qwen license; not redistributed here.
