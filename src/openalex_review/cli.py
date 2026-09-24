from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .common import ensure_directories, env_api_key, project_root, run_id_now
from .config import load_search_config, override_config
from .control import import_screening_decisions, init_control


def _config_from_args(args):
    path = Path(args.config)
    if not path.is_absolute():
        path = project_root() / path
    config = load_search_config(path)
    return override_config(
        config,
        from_date=getattr(args, "from_publication_date", None),
        to_date=getattr(args, "to_publication_date", None),
        max_records=getattr(args, "max_records", None),
        progress_every=getattr(args, "progress_every", None),
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="openalex-review")
    parser.add_argument("--root", help="Raiz do projeto. Por padrao, o diretorio atual.")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("check", help="Verifica ambiente e credenciais.")

    validate = sub.add_parser("validate-config", help="Valida um YAML de busca.")
    validate.add_argument("--config", required=True)

    for name in ("count", "collect"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--config", required=True)
        cmd.add_argument("--from-publication-date")
        cmd.add_argument("--to-publication-date")
        cmd.add_argument("--max-records", type=int)
        cmd.add_argument("--progress-every", type=int)
        if name == "collect":
            cmd.add_argument("--run-id")
            cmd.add_argument("--overwrite", action="store_true")

    sub.add_parser("build-db")
    export = sub.add_parser("export")
    export.add_argument("--filter", default="all", choices=["all", "open_access", "with_abstract", "with_doi", "not_retracted"])
    sub.add_parser("report")
    seeds = sub.add_parser("validate-seeds")
    seeds.add_argument("--fail-on-missing", action="store_true")
    control = sub.add_parser("init-control")
    control.add_argument("--overwrite", action="store_true")

    screening = sub.add_parser("import-screening", help="Importa decisoes do ASReview para CSV e DuckDB.")
    screening.add_argument("--input", required=True, help="CSV exportado pelo ASReview.")
    screening.add_argument("--reviewer", required=True, help="Identificador do revisor ou da rodada.")
    screening.add_argument("--stage", default="titulo_resumo")
    screening.add_argument("--decision-column", help="Coluna com decisao/label; detectada automaticamente.")
    screening.add_argument("--replace", action="store_true", help="Substitui decisoes anteriores da mesma etapa e revisor.")

    pipeline = sub.add_parser("pipeline")
    pipeline.add_argument("--config", required=True)
    pipeline.add_argument("--run-id")
    pipeline.add_argument("--max-records", type=int)
    pipeline.add_argument("--from-publication-date")
    pipeline.add_argument("--to-publication-date")
    pipeline.add_argument("--progress-every", type=int)
    pipeline.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.root:
        os.environ["OPENALEX_REVIEW_ROOT"] = str(Path(args.root).resolve())
    root = project_root()
    load_dotenv(root / ".env")
    ensure_directories(root)

    if args.command == "check":
        import platform
        print(f"Python: {platform.python_version()}")
        print(f"Projeto: {root}")
        env_api_key()
        print("OPENALEX_API_KEY: configurada")
        return

    if args.command == "validate-config":
        config = _config_from_args(args)
        print(f"Projeto: {config.project_name}")
        print(f"Consultas validas: {len(config.queries)}")
        for spec in config.queries:
            print(f"- {spec.id} [{spec.mode}] max={spec.max_records}")
        return

    if args.command in {"count", "collect", "pipeline"}:
        env_api_key()
        try:
            import pyalex
        except ImportError as exc:
            raise RuntimeError("Dependencia pyalex nao instalada.") from exc
        pyalex.config.api_key = env_api_key()
        pyalex.config.email = None
        config = _config_from_args(args)

    if args.command == "count":
        from .collector import count_config
        count_config(config)
    elif args.command == "collect":
        from .collector import collect_config
        collect_config(config, args.run_id or run_id_now(), overwrite=args.overwrite, root=root)
    elif args.command == "build-db":
        from .database import build_database
        print(build_database(root))
    elif args.command == "export":
        from .exporter import export_records
        print(f"Exportados: {export_records(args.filter, root)}")
    elif args.command == "report":
        from .report import generate_report
        print(generate_report(root))
    elif args.command == "validate-seeds":
        from .report import validate_seeds
        found, missing = validate_seeds(root, args.fail_on_missing)
        print(f"Recuperadas: {len(found)}")
        print(f"Nao recuperadas: {len(missing)}")
        for doi in missing:
            print(f"- {doi}")
    elif args.command == "init-control":
        for path in init_control(root, args.overwrite):
            print(path)
    elif args.command == "import-screening":
        source = Path(args.input)
        if not source.is_absolute():
            source = root / source
        result = import_screening_decisions(
            source,
            reviewer=args.reviewer,
            stage=args.stage,
            decision_column=args.decision_column,
            root=root,
            replace=args.replace,
        )
        print(
            f"Linhas: {result.source_rows} | Importadas: {result.imported} | "
            f"Sem decisao: {result.skipped_unlabeled} | Ja existentes: {result.skipped_existing}\n"
            f"Controle: {result.control_path}\nErros: {result.errors_path}"
        )
    elif args.command == "pipeline":
        from .collector import collect_config
        from .database import build_database
        from .exporter import export_records
        from .report import generate_report
        collect_config(config, args.run_id or run_id_now(), overwrite=args.overwrite, root=root)
        build_database(root)
        export_records("all", root)
        generate_report(root)
        init_control(root)
        print("Pipeline concluido.")
    else:
        parser.error("Comando nao implementado.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
