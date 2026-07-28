type Props = {
  titulo: string;
};

export default function ModuloEnConstruccion({ titulo }: Props) {
  return (
    <div className="page-content">
      <header className="page-header">
        <h1>{titulo}</h1>
      </header>
      <div className="placeholder">
        <p className="placeholder-title">Módulo en construcción</p>
        <p className="sub">
          Esta sección se integrará al portal Sistemas Pañol en una próxima etapa.
        </p>
      </div>
    </div>
  );
}
