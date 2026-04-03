"""Database loader for Form 13F data."""

from pathlib import Path
from typing import Dict, Set
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from tqdm import tqdm

from ..ingestion.tsv_parser import Form13FTSVParser
from ..models.filing import ParsedFiling
from .models import Manager, Issuer, Filing, Holding
from .session import SessionLocal


class Form13FDatabaseLoader:
    """
    Loads parsed Form 13F data into PostgreSQL.

    Handles deduplication of managers and issuers, and bulk inserts
    for performance.
    """

    def __init__(self, session: Session | None = None):
        """
        Initialize loader.

        Args:
            session: Optional SQLAlchemy session. If None, creates new session.
        """
        self.session = session or SessionLocal()
        self._should_close_session = session is None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        if self._should_close_session:
            self.session.close()

    def load_from_tsv_folder(self, folder_path: Path | str, show_progress: bool = True) -> Dict[str, int]:
        """
        Load Form 13F data from TSV files into database.

        Args:
            folder_path: Path to folder containing TSV files
            show_progress: Whether to show progress bars

        Returns:
            Dictionary with counts of loaded records

        """
        folder_path = Path(folder_path)

        # Parse TSV files
        print(f"Parsing TSV files from {folder_path}...")
        parser = Form13FTSVParser(folder_path)
        parsed_filings = parser.parse_all_filings()

        print(f"\nFound {len(parsed_filings):,} filings to load")

        # Load data
        stats = self.load_parsed_filings(parsed_filings, show_progress=show_progress)

        return stats

    def load_parsed_filings(
        self,
        parsed_filings: list[ParsedFiling],
        show_progress: bool = True
    ) -> Dict[str, int]:
        """
        Load parsed filings into database.

        Args:
            parsed_filings: List of ParsedFiling objects
            show_progress: Whether to show progress bars

        Returns:
            Dictionary with counts of loaded records
        """
        stats = {
            "managers": 0,
            "issuers": 0,
            "filings": 0,
            "holdings": 0,
        }

        # Step 1: Extract and deduplicate managers
        print("\n1. Loading managers...")
        managers = self._extract_managers(parsed_filings)
        stats["managers"] = self._load_managers(managers, show_progress)

        # Step 2: Extract and deduplicate issuers
        print("\n2. Loading issuers...")
        issuers = self._extract_issuers(parsed_filings)
        stats["issuers"] = self._load_issuers(issuers, show_progress)

        # Step 3: Load filings (returns set of newly inserted accession numbers)
        print("\n3. Loading filings...")
        new_accessions = self._get_new_accession_numbers(parsed_filings)
        stats["filings"] = self._load_filings(parsed_filings, show_progress)

        # Step 4: Load holdings (only for new filings)
        print("\n4. Loading holdings...")
        new_filings = [f for f in parsed_filings if f.metadata.accession_number in new_accessions]
        skipped = len(parsed_filings) - len(new_filings)
        if skipped > 0:
            print(f"   Skipping holdings for {skipped:,} existing filings")
        stats["holdings"] = self._load_holdings(new_filings, show_progress)

        # Commit transaction
        self.session.commit()
        print("\n✓ All data loaded successfully!")

        return stats

    def _get_new_accession_numbers(self, parsed_filings: list[ParsedFiling]) -> Set[str]:
        """Determine which accession numbers don't exist in the database yet."""
        all_accessions = {f.metadata.accession_number for f in parsed_filings}

        # Query existing accession numbers in batches
        existing = set()
        accession_list = list(all_accessions)
        batch_size = 500
        for i in range(0, len(accession_list), batch_size):
            batch = accession_list[i:i + batch_size]
            rows = self.session.query(Filing.accession_number).filter(
                Filing.accession_number.in_(batch)
            ).all()
            existing.update(row[0] for row in rows)

        new = all_accessions - existing
        print(f"   Found {len(new):,} new filings out of {len(all_accessions):,} total")
        return new

    def _extract_managers(self, parsed_filings: list[ParsedFiling]) -> Dict[str, str]:
        """Extract unique managers from filings."""
        managers = {}
        for filing in parsed_filings:
            cik = filing.metadata.cik
            name = filing.metadata.manager_name
            if cik not in managers:
                managers[cik] = name

        return managers

    def _extract_issuers(self, parsed_filings: list[ParsedFiling]) -> Dict[str, Dict[str, str | None]]:
        """Extract unique issuers from holdings."""
        issuers = {}
        for filing in parsed_filings:
            for holding in filing.holdings:
                cusip = holding.cusip
                if cusip not in issuers:
                    issuers[cusip] = {
                        "name": holding.issuer_name,
                        "figi": holding.figi,
                    }

        return issuers

    def _load_managers(self, managers: Dict[str, str], show_progress: bool) -> int:
        """Load managers using upsert (INSERT ... ON CONFLICT)."""
        manager_dicts = [
            {"cik": cik, "name": name}
            for cik, name in managers.items()
        ]

        if not manager_dicts:
            return 0

        # Use PostgreSQL upsert
        stmt = insert(Manager).values(manager_dicts)
        stmt = stmt.on_conflict_do_update(
            index_elements=['cik'],
            set_={"name": stmt.excluded.name}
        )

        self.session.execute(stmt)
        return len(manager_dicts)

    def _load_issuers(self, issuers: Dict[str, Dict[str, str | None]], show_progress: bool) -> int:
        """Load issuers using upsert."""
        issuer_dicts = [
            {"cusip": cusip, "name": data["name"], "figi": data["figi"]}
            for cusip, data in issuers.items()
        ]

        if not issuer_dicts:
            return 0

        # Use PostgreSQL upsert
        stmt = insert(Issuer).values(issuer_dicts)
        stmt = stmt.on_conflict_do_update(
            index_elements=['cusip'],
            set_={
                "name": stmt.excluded.name,
                "figi": stmt.excluded.figi,
            }
        )

        self.session.execute(stmt)
        return len(issuer_dicts)

    def _load_filings(self, parsed_filings: list[ParsedFiling], show_progress: bool) -> int:
        """Load filings using upsert (skip duplicates)."""
        filing_dicts = []

        iterator = tqdm(parsed_filings, desc="Preparing filings") if show_progress else parsed_filings

        for filing in iterator:
            filing_dict = {
                "accession_number": filing.metadata.accession_number,
                "cik": filing.metadata.cik,
                "filing_date": filing.metadata.filing_date,
                "period_of_report": filing.metadata.period_of_report,
                "submission_type": filing.metadata.submission_type,
                "report_type": filing.metadata.report_type,
                "total_value": filing.metadata.total_value,
                "number_of_holdings": filing.metadata.number_of_holdings,
            }
            filing_dicts.append(filing_dict)

        if not filing_dicts:
            return 0

        # Upsert in batches - skip existing filings
        batch_size = 1000
        inserted = 0
        for i in range(0, len(filing_dicts), batch_size):
            batch = filing_dicts[i:i + batch_size]
            stmt = insert(Filing).values(batch)
            stmt = stmt.on_conflict_do_nothing(index_elements=['accession_number'])
            result = self.session.execute(stmt)
            inserted += result.rowcount
        return inserted

    def _load_holdings(self, parsed_filings: list[ParsedFiling], show_progress: bool) -> int:
        """Load holdings using bulk insert."""
        holding_dicts = []

        iterator = tqdm(parsed_filings, desc="Preparing holdings") if show_progress else parsed_filings

        for filing in iterator:
            for holding in filing.holdings:
                holding_dict = {
                    "accession_number": holding.accession_number,
                    "cusip": holding.cusip,
                    "title_of_class": holding.title_of_class,
                    "value": holding.value,
                    "shares_or_principal": holding.shares_or_principal,
                    "sh_or_prn": holding.sh_or_prn,
                    "investment_discretion": holding.investment_discretion,
                    "put_call": holding.put_call,
                    "voting_authority_sole": holding.voting_authority_sole,
                    "voting_authority_shared": holding.voting_authority_shared,
                    "voting_authority_none": holding.voting_authority_none,
                }
                holding_dicts.append(holding_dict)

        if not holding_dicts:
            return 0

        # Bulk insert in batches for better performance
        batch_size = 5000
        for i in range(0, len(holding_dicts), batch_size):
            batch = holding_dicts[i:i + batch_size]
            self.session.bulk_insert_mappings(Holding, batch)

        return len(holding_dicts)


def load_from_tsv_cli(folder_path: str, database_url: str | None = None):
    """
    CLI function to load data from TSV files.

    Args:
        folder_path: Path to folder containing TSV files
        database_url: Optional database URL (uses env var if not provided)
    """
    import os
    from dotenv import load_dotenv

    load_dotenv()

    if database_url:
        os.environ["DATABASE_URL"] = database_url

    with Form13FDatabaseLoader() as loader:
        stats = loader.load_from_tsv_folder(folder_path, show_progress=True)

    print("\n" + "=" * 60)
    print("LOAD COMPLETE")
    print("=" * 60)
    print(f"Managers:  {stats['managers']:>10,}")
    print(f"Issuers:   {stats['issuers']:>10,}")
    print(f"Filings:   {stats['filings']:>10,}")
    print(f"Holdings:  {stats['holdings']:>10,}")
    print("=" * 60)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python -m src.db.loader <path_to_tsv_folder>")
        sys.exit(1)

    load_from_tsv_cli(sys.argv[1])
