type Props = {
  sectores: string[];
  activo: string;
  onChange: (sector: string) => void;
};

export default function SectorTabs({ sectores, activo, onChange }: Props) {
  return (
    <nav className="minuta-sector-tabs" aria-label="Sectores">
      {sectores.map((s) => (
        <button
          key={s}
          type="button"
          className={`minuta-sector-tab${activo === s ? " active" : ""}`}
          onClick={() => onChange(s)}
        >
          {s}
        </button>
      ))}
    </nav>
  );
}
