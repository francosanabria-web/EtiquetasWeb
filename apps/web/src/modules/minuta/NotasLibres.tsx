type Props = {
  notas: string;
  onChange: (v: string) => void;
};

export default function NotasLibres({ notas, onChange }: Props) {
  return (
    <section className="minuta-section">
      <h2>Notas libres</h2>
      <textarea
        className="minuta-textarea"
        value={notas}
        onChange={(e) => onChange(e.target.value)}
        rows={5}
        placeholder="Observaciones, acuerdos, pendientes…"
      />
    </section>
  );
}
