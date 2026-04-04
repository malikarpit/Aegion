import asyncio
import os
import glob
import re
from pathlib import Path
from typing import Optional

# Setup path to import app modules
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.core.config import settings
from app.adapters.persistence.event_store import FileEventStore
from app.services.chronos.timeline import get_timeline_service, ArchitectureTimelineService

# Regex patterns for ADR parsing
TITLE_PATTERN = re.compile(r"^#\s+(.+)$", re.MULTILINE)
STATUS_PATTERN = re.compile(r"Status:\s*(.+)$", re.MULTILINE | re.IGNORECASE)
CONTEXT_PATTERN = re.compile(r"## Context\s+(.+?)##", re.DOTALL)
DECISION_PATTERN = re.compile(r"## Decision\s+(.+?)##", re.DOTALL)
CONSEQUENCES_PATTERN = re.compile(r"## Consequences\s+(.+)", re.DOTALL)

async def parse_adr(file_path: Path) -> dict:
    content = file_path.read_text()
    
    title_match = TITLE_PATTERN.search(content)
    status_match = STATUS_PATTERN.search(content)
    context_match = CONTEXT_PATTERN.search(content)
    decision_match = DECISION_PATTERN.search(content)
    consequences_match = CONSEQUENCES_PATTERN.search(content)
    
    return {
        "title": title_match.group(1).strip() if title_match else "Untitled ADR",
        "status": status_match.group(1).strip() if status_match else "Proposed",
        "context": context_match.group(1).strip() if context_match else "",
        "decision": decision_match.group(1).strip() if decision_match else "",
        "consequences": consequences_match.group(1).strip() if consequences_match else "",
        "filename": file_path.name
    }

async def main():
    print("🔄 Starting ADR Synchronization...")
    
    # 1. Initialize Service & Hydrate
    # Force local mode for script
    os.makedirs(".aegion", exist_ok=True)
    event_store = FileEventStore(".aegion/events.jsonl")
    service = get_timeline_service(event_store)
    await service.hydrate()
    
    existing_adrs = await service.list_adrs()
    existing_titles = {adr.title for adr in existing_adrs}
    
    print(f"📊 Found {len(existing_adrs)} existing ADRs in Event Store.")
    
    # 2. Scan Docs
    docs_dir = Path("../docs/adr")
    if not docs_dir.exists():
        print(f"⚠️  Docs directory not found at {docs_dir.resolve()}")
        return

    adr_files = list(docs_dir.glob("*.md"))
    print(f"📂 Found {len(adr_files)} Markdown ADRs in {docs_dir}.")
    
    added_count = 0
    skipped_count = 0
    
    for adr_file in adr_files:
        if adr_file.name == "README.md" or adr_file.name == "template.md":
            continue
            
        data = await parse_adr(adr_file)
        
        if data["title"] in existing_titles:
            print(f"⏭️  Skipping existing: {data['title']}")
            skipped_count += 1
            continue
            
        print(f"➕ Importing: {data['title']}")
        
        # Create
        adr = await service.create_adr(
            title=data["title"],
            context=data["context"],
            decision=data["decision"],
            rationale="Imported from markdown",
            created_by="system_migration",
            workspace_id="default"
        )
        
        # Update Status
        status = data["status"].lower()
        if "accepted" in status:
            await service.accept_adr(
                adr_id=adr.adr_id,
                accepted_by="system_migration",
                workspace_id="default",
                expected_version=adr.version
            )
        elif "deprecated" in status:
             await service.deprecate_adr(
                adr_id=adr.adr_id,
                deprecated_by="system_migration",
                workspace_id="default",
                reason="Imported as deprecated",
                expected_version=adr.version
            )
            
        added_count += 1

    print("-" * 40)
    print(f"✅ Sync Complete.")
    print(f"   Added:   {added_count}")
    print(f"   Skipped: {skipped_count}")

if __name__ == "__main__":
    asyncio.run(main())
