# Pass 4 Review

Target script: `evidence/skript_probe_pass4_mne.py`

## Acceptance Check

- Goal obvious in the first lines: yes
- Main scientific choices justified in comments: yes
- MNE-native calls used unless there was a clear reason not to: yes
- Helper calls do not hide unexplained logic: yes
- Script reads linearly and is easy to scan: yes
- Script avoids artificial line-count compression: yes

## Result

- This probe matches the revised `SKRIPT.md` better than pass 2.
- The main improvement is not shorter code; it is visible scientific choices plus MNE-native logic.
- The script remains simple enough to scan without opening `preprocessing.py`.
