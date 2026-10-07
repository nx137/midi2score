from pathlib import Path
from collections import Counter
import subprocess, json, mido
from lxml import etree
from lxml.etree import _Element  # noqa

DATASET = Path(r"E:\midi2score\data\asap-dataset")
MS = Path(r"D:\MuseScore 4\bin\MuseScore4.exe")
TARGETS = [
    "Prokofiev/Toccata/xml_score.musicxml",
    "Schubert/Impromptu_op.90_D.899/3/xml_score.musicxml",
]
OUT = Path(r"E:\midi2score\evidence\R1\T1-probe")
OUT.mkdir(parents=True, exist_ok=True)

def parents(elem):
    chain = []
    p = elem.getparent()
    while p is not None and len(chain) < 3:
        chain.append(etree.QName(p).localname)
        p = p.getparent()
    return " < ".join(chain)

for rel in TARGETS:
    xml = DATASET / rel
    root = etree.parse(str(xml)).getroot()
    elems = root.xpath(".//*[local-name()='pedal']")
    print("="*100)
    print(rel)
    print(f"  musicxml version = {root.get('version')}")
    print(f"  parts = {len(root.xpath('.//*[local-name()=\"score-part\"]'))}, staves(score-partwise) = {len(root.xpath('.//*[local-name()=\"staves\"]'))}")
    print(f"  pedal elements = {len(elems)}  types = {dict(Counter(e.get('type') for e in elems))}")
    for i, e in enumerate(elems[:6]):
        print(f"    #{i} type={e.get('type')} line={e.get('line')} staff={e.get('staff')} number={e.get('number')} parent={parents(e)}")
    if len(elems) > 6:
        print(f"    ... (+{len(elems)-6} more)")

    mid = OUT / (rel.replace('/', '__').replace('.musicxml', '') + ".mid")
    for run in (1, 2):
        mid.unlink(missing_ok=True)
        cmd = [str(MS), "-f", "-o", str(mid), str(xml)]
        p = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                           timeout=180, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        n_cc64 = 0; controls = Counter(); channels = Counter(); total = 0
        if mid.is_file():
            mf = mido.MidiFile(str(mid))
            for tr in mf.tracks:
                for msg in tr:
                    total += 1
                    if msg.type == "control_change":
                        controls[msg.control] += 1
                        channels[msg.channel] += 1
                        if msg.control == 64:
                            n_cc64 += 1
        print(f"  run{run}: exit={p.returncode} out_exists={mid.is_file()} total_msgs={total} cc64={n_cc64} "
              f"all_controls={dict(sorted(controls.items()))} channels={dict(sorted(channels.items()))}")
        print(f"         stdout={p.stdout.strip()[:120]!r} stderr={p.stderr.strip()[:120]!r}")