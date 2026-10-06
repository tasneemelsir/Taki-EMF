import { useMemo, useState } from 'react';
import { ExternalLink, Search } from 'lucide-react';
import { Card, PageHead, Pill, Tabs } from '@/components/ui';
import { fmt, sci } from '@/lib/format';
import { useStore } from '@/lib/store';
import { Loading } from './common';

const KIND: Record<string, [string, 'blue' | 'green' | 'amber' | 'teal' | undefined]> = {
  standard: ['Standard', 'blue'], journal: ['Journal paper', 'green'], textbook: ['Textbook', 'green'],
  'org-publication': ['Organisation report', 'teal'], dataset: ['Bundled dataset', 'teal'], web: ['Web / patent', 'amber'],
};

export default function LibraryPage() {
  const lib = useStore((s) => s.library);
  const config = useStore((s) => s.config);
  const [tab, setTab] = useState<'refs' | 'materials' | 'standards'>('refs');
  const [q, setQ] = useState('');
  const [topic, setTopic] = useState('All');
  const refs = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (lib?.references ?? []).filter((r) => (topic === 'All' || r.topic === topic) && (!needle || [r.title, r.authors, r.venue, r.findings, r.materials, r.method, r.used_for].join(' ').toLowerCase().includes(needle)));
  }, [lib, q, topic]);
  if (!lib) return <div className="page"><Loading /></div>;
  const f60 = (config?.corridor.freq_hz ?? 50) >= 55;
  const refTitle = (id: string) => lib.references.find((r) => r.id === id);

  return (
    <div className="page">
      <PageHead title="Research library" lede="The sources behind the standards, the field methods, the shielding models and the material data. Each entry says what kind of record it is and where the app uses it. Identifiers are included only where they are known with confidence." />
      <Tabs value={tab} onChange={setTab} options={[{ value: 'refs', label: `References (${lib.references.length})` }, { value: 'materials', label: 'Shielding materials' }, { value: 'standards', label: 'Exposure standards' }]} />

      {tab === 'refs' && (
        <>
          <div className="row wrap gap-12 mb-12">
            <div className="input-unit" style={{ flex: '1 1 280px', maxWidth: 420 }}>
              <input className="input" placeholder="Search title, author, material, method…" value={q} onChange={(e) => setQ(e.target.value)} style={{ paddingLeft: 30, paddingRight: 9 }} />
              <span className="u" style={{ left: 9, right: 'auto' }}><Search size={14} /></span>
            </div>
            <div className="chips">
              {['All', ...lib.reference_topics].map((t) => <button key={t} className={`chip blue ${topic === t ? 'on' : ''}`} onClick={() => setTopic(t)}>{t}</button>)}
            </div>
          </div>
          {refs.length === 0 && <p className="small muted">No reference matches that search.</p>}
          <div className="col gap-8">
            {refs.map((r) => {
              const k = KIND[r.verification] ?? [r.verification, undefined];
              return (
                <Card key={r.id} className="tight">
                  <div className="row wrap gap-4 mb-8"><Pill tone={k[1]}>{k[0]}</Pill><Pill>{r.topic}</Pill>{r.freq_range && <Pill>{r.freq_range}</Pill>}</div>
                  <div style={{ fontWeight: 600 }}>{r.title}</div>
                  <div className="small muted">{r.authors} · {r.venue} · {r.year}</div>
                  <p className="small mt-8">{r.findings}</p>
                  <div className="small muted">
                    {r.method && <>Method: {r.method}. </>}{r.materials && <>Materials: {r.materials}. </>}
                    {r.used_for && <><b style={{ color: 'var(--ink)' }}>Used for:</b> {r.used_for}</>}
                  </div>
                  <div className="row wrap gap-12 mt-8 small">
                    {r.doi && <span className="mono tiny">doi:{r.doi}</span>}
                    {r.url && <a href={r.url} target="_blank" rel="noreferrer noopener" className="row gap-4"><ExternalLink size={12} />Source</a>}
                  </div>
                </Card>
              );
            })}
          </div>
        </>
      )}

      {tab === 'materials' && (
        <>
          <p className="small muted mb-12">Conductivity and permeability of pure metals are physical constants (“verified”). Steels, alloys, composites and building materials vary widely by grade, field strength and moisture (“assumed”): treat results with them as indicative, or enter measured values as a custom material.</p>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Material</th><th>Category</th><th className="num">σ (S/m)</th><th className="num">ρ (Ω·m)</th><th className="num">µr</th><th className="num">Skin depth {f60 ? '60' : '50'} Hz</th><th>Data</th><th>Mechanism and limits</th><th>Sources</th></tr></thead>
              <tbody>
                {lib.shield_materials.map((m) => (
                  <tr key={m.id}>
                    <td style={{ fontWeight: 600 }}>{m.label}<div className="tiny muted" style={{ fontWeight: 400 }}>{m.applications}</div></td>
                    <td className="muted">{m.category}</td>
                    <td className="num">{sci(m.sigma)}</td><td className="num">{m.resistivity ? sci(m.resistivity) : '—'}</td><td className="num">{fmt(m.mu_r, 4)}</td>
                    <td className="num">{Number.isFinite(f60 ? m.skin_depth_60_mm : m.skin_depth_50_mm) ? `${fmt(f60 ? m.skin_depth_60_mm : m.skin_depth_50_mm)} mm` : '—'}</td>
                    <td><Pill tone={m.quality === 'verified' ? 'green' : 'amber'}>{m.quality}</Pill></td>
                    <td className="small" style={{ minWidth: 240 }}>{m.mechanisms}<div className="muted">{m.limitations}</div></td>
                    <td className="small">{m.ref_ids.length ? m.ref_ids.map((id) => <div key={id} title={refTitle(id)?.title}>{refTitle(id)?.authors.split(',')[0]} {refTitle(id)?.year}</div>) : <span className="muted">—</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <Card className="mt-12" title="Empirical building-fabric estimates" sub="Taki's original literature model">
            <div className="table-wrap">
              <table className="tbl">
                <thead><tr><th>Class</th><th className="num">B reduction</th><th className="num">E reduction</th><th>Why</th></tr></thead>
                <tbody>{lib.building_materials.filter((m) => m.key !== 'none').map((m) => (
                  <tr key={m.key}><td style={{ fontWeight: 600 }}>{m.label}</td><td className="num">{m.b_pct}% <span className="muted">({m.b_range[0]}–{m.b_range[1]})</span></td><td className="num">{m.e_pct}% <span className="muted">({m.e_range[0]}–{m.e_range[1]})</span></td><td className="small">{m.mechanism}</td></tr>
                ))}</tbody>
              </table>
            </div>
            <p className="small muted mt-8">These percentages are engineering estimates from the web sources listed under “Empirical shielding estimates”. The physical model does not use them.</p>
          </Card>
        </>
      )}

      {tab === 'standards' && (
        <>
          <p className="small muted mb-12">Limits at 50 Hz and 60 Hz. Entries marked “verify” were transcribed from secondary sources and must be checked against the primary document before certification.</p>
          <div className="table-wrap">
            <table className="tbl">
              <thead><tr><th>Standard</th><th>Applies to</th><th className="num">B 50 Hz (µT)</th><th className="num">E 50 Hz (kV/m)</th><th className="num">B 60 Hz</th><th className="num">E 60 Hz</th><th>Notes and source</th></tr></thead>
              <tbody>
                {lib.standards.map((s) => (
                  <tr key={s.id}>
                    <td style={{ fontWeight: 600 }}>{s.name}<div className="row wrap gap-4 mt-4">{s.kind === 'precautionary' && <Pill tone="teal">precautionary</Pill>}{s.population === 'occupational' && <Pill>occupational</Pill>}{s.needs_verification && <Pill tone="amber">verify</Pill>}</div></td>
                    <td className="muted">{s.jurisdiction}<div className="tiny">{s.year}</div></td>
                    <td className="num">{s.b50 !== null ? fmt(s.b50, 4) : '—'}</td><td className="num">{s.e50 !== null ? fmt(s.e50, 3) : '—'}</td>
                    <td className="num">{s.b60 !== null ? fmt(s.b60, 4) : '—'}</td><td className="num">{s.e60 !== null ? fmt(s.e60, 3) : '—'}</td>
                    <td className="small" style={{ minWidth: 280 }}>{s.notes}<div className="muted mt-4">{s.source}</div>{s.url && <a href={s.url} target="_blank" rel="noreferrer noopener" className="row gap-4 mt-4"><ExternalLink size={12} />Source</a>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
