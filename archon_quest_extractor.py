#!/usr/bin/env python3
"""
Genshin Impact Archon Quest Dialogue Extractor v2
Combines two extraction methods:
1. DialogExcelConfigData (old chapters: Mondstadt, Liyue, Inazuma, Sumeru, Natlan)
2. CodexQuest files (new chapters: Fontaine and beyond)
"""

import argparse
import json
import os
import random
from datetime import datetime
from pathlib import Path
from collections import defaultdict

class ArchonQuestExtractorV2:
    def __init__(self, data_dir='GenshinScripts/data', repo_dir='AnimeGameData', textmap_lang='CHS'):
        self.data_dir = Path(data_dir)
        self.repo_dir = Path(repo_dir)
        self.excel_dir = self.data_dir / 'Excel'
        self.textmap_path = self.data_dir / 'TextMap' / f'TextMap{textmap_lang}.json'
        self.codex_dir = self.repo_dir / 'BinOutput' / 'CodexQuest'

        print("Loading data files...")
        self.textmap = self.load_json(self.textmap_path)
        self.chapters = self.load_json(self.excel_dir / 'ChapterExcelConfigData.json')
        self.main_quests = self.load_json(self.excel_dir / 'MainQuestExcelConfigData.json')
        self.quests = self.load_json(self.excel_dir / 'QuestExcelConfigData.json')
        self.talks = self.load_json(self.excel_dir / 'TalkExcelConfigData.json')
        self.dialogs = self.load_json(self.excel_dir / 'DialogExcelConfigData.json')
        self.npcs = self.load_json(self.excel_dir / 'NpcExcelConfigData.json')

        # Build lookup dicts
        self.talk_dict = {t['id']: t for t in self.talks if isinstance(t, dict) and 'id' in t}
        self.dialog_dict = {}
        for d in self.dialogs:
            if not isinstance(d, dict):
                continue
            dialog_id = d.get('GFLDJMJKIKE') or d.get('id')
            if dialog_id:
                self.dialog_dict[dialog_id] = d
        self.npc_dict = {n['id']: n for n in self.npcs if isinstance(n, dict) and 'id' in n}

        # Build main quest lookup
        self.main_quest_dict = {mq['id']: mq for mq in self.main_quests if isinstance(mq, dict) and 'id' in mq}

        print(f"Loaded: {len(self.chapters)} chapters, {len(self.main_quests)} main quests, {len(self.dialogs)} dialogs")
        print(f"CodexQuest dir: {self.codex_dir}")
    
    def load_json(self, filepath):
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return []
    
    def get_text(self, hash_value):
        """Convert text hash to actual text"""
        if not hash_value:
            return ""
        if isinstance(self.textmap, dict):
            return self.textmap.get(str(hash_value), f"[Missing:{hash_value}]")
        return f"[Missing:{hash_value}]"
    
    def get_archon_chapters(self):
        """Get all Archon Quest chapters"""
        chapters = [ch for ch in self.chapters if isinstance(ch, dict) and ch.get('questType') == 'AQ']
        return sorted(chapters, key=lambda x: x.get('id', 0))
    
    def get_chapter_main_quests(self, chapter_id):
        """Get main quests for a chapter using series or chapterId field"""
        return sorted([mq for mq in self.main_quests 
                      if mq.get('series') == chapter_id or mq.get('chapterId') == chapter_id],
                     key=lambda x: x.get('id', 0))
    
    def extract_from_codexquest(self, quest_id):
        """Extract dialogues from CodexQuest file"""
        codex_file = self.codex_dir / f"{quest_id}.json"
        
        if not codex_file.exists():
            return None
        
        try:
            with open(codex_file, 'r', encoding='utf-8') as f:
                quest_data = json.load(f)
        except Exception as e:
            print(f"  Error loading CodexQuest {quest_id}: {e}")
            return None
        
        dialogues = []
        
        # GFLHMKOOHHA contains main dialogue sections
        if 'GFLHMKOOHHA' in quest_data:
            sections = quest_data['GFLHMKOOHHA']
            
            for section in sections:
                if 'JKNIDKEDDMB' in section:
                    nodes = section['JKNIDKEDDMB']
                    
                    for node in nodes:
                        speaker_data = node.get('LKJMACGGCNI', {})
                        speaker_hash = speaker_data.get('MANCOJCEIMH', 0)
                        speaker = self.get_text(speaker_hash) if speaker_hash else '旁白'
                        
                        if speaker.startswith('[') or not speaker:
                            speaker = '旁白'
                        
                        if 'IINLCABCIDE' in node:
                            for dialog_entry in node['IINLCABCIDE']:
                                dialog_id = dialog_entry.get('GEJLBGLBCOO', 0)
                                text_data = dialog_entry.get('GLMJHDNIGID', {})
                                text_hash = text_data.get('MANCOJCEIMH', 0)
                                
                                if text_hash:
                                    text = self.get_text(text_hash)
                                    dialogues.append({
                                        'id': dialog_id,
                                        'text': text,
                                        'speaker': speaker
                                    })
        
        return dialogues if dialogues else None
    
    def infer_speaker(self, text):
        """Infer speaker from dialogue text (basic heuristic)"""
        # This is a simple heuristic - CodexQuest doesn't have clear speaker info
        # Could be improved by analyzing dialogue patterns
        if text.startswith('派蒙：'):
            return '派蒙'
        # Add more patterns as needed
        return '未知'
    
    def extract_from_dialog_tree(self, quest_id):
        """Extract dialogues using old method (DialogExcelConfigData)"""
        # Find talk configs for this quest
        quest_talks = [t for t in self.talks if t.get('questId') == quest_id]
        
        if not quest_talks:
            return None
        
        dialogues = []
        
        for talk in quest_talks:
            init_dialog = talk.get('initDialog', 0)
            
            if init_dialog:
                # Try to find dialog with ID prefix variants
                dialog_ids_to_try = [
                    init_dialog,
                    int(f"6{init_dialog}"),  # Newer versions use prefix '6'
                ]
                
                for dialog_id in dialog_ids_to_try:
                    if dialog_id in self.dialog_dict:
                        talk_dialogues = self.extract_dialog_tree(dialog_id)
                        dialogues.extend(talk_dialogues)
                        break
        
        return dialogues if dialogues else None
    
    def extract_dialog_tree(self, dialog_id, visited=None):
        """Recursively extract dialogue tree"""
        if visited is None:
            visited = set()
        
        if dialog_id in visited:
            return []
        
        visited.add(dialog_id)
        
        dialog = self.dialog_dict.get(dialog_id)
        if not dialog:
            return []
        
        dialogues = []
        
        # Get current dialogue
        text_hash = dialog.get('talkContentTextMapHash', 0)
        if text_hash:
            text = self.get_text(text_hash)
            speaker = self.get_speaker_name(dialog)
            
            dialogues.append({
                'id': dialog_id,
                'speaker': speaker,
                'text': text
            })
        
        # Follow next dialogs
        next_dialogs = dialog.get('nextDialogs', [])
        for next_id in next_dialogs:
            dialogues.extend(self.extract_dialog_tree(next_id, visited))
        
        return dialogues
    
    def get_speaker_name(self, dialog):
        """Get speaker name from dialog"""
        talk_role = dialog.get('talkRole', {})
        role_type = talk_role.get('type', '')
        
        if role_type == 'TALK_ROLE_PLAYER':
            return '旅行者'
        
        role_id = talk_role.get('id', 0)
        if role_id:
            npc = self.npc_dict.get(role_id, {})
            name_hash = npc.get('nameTextMapHash', 0)
            if name_hash:
                return self.get_text(name_hash)
        
        return '未知'
    
    def extract_chapter(self, chapter):
        """Extract all dialogues for a chapter using hybrid approach"""
        chapter_id = chapter.get('id', 0)
        chapter_num_hash = chapter.get('chapterNumTextMapHash', 0)
        chapter_title_hash = chapter.get('chapterTitleTextMapHash', 0)
        
        chapter_num = self.get_text(chapter_num_hash)
        chapter_title = self.get_text(chapter_title_hash)
        
        print(f"\n{'='*60}")
        print(f"Processing Chapter {chapter_id}: {chapter_num} {chapter_title}")
        print(f"{'='*60}")
        
        # Get main quests for this chapter
        main_quests = self.get_chapter_main_quests(chapter_id)
        
        if not main_quests:
            print(f"  No main quests found for chapter {chapter_id}")
            return None
        
        chapter_output = []
        chapter_output.append("=" * 60)
        chapter_output.append(chapter_num)
        chapter_output.append(chapter_title)
        chapter_output.append(f"Chapter ID: {chapter_id}")
        chapter_output.append("=" * 60)
        chapter_output.append("")
        
        for main_quest in main_quests:
            quest_id = main_quest.get('id', 0)
            title_hash = main_quest.get('titleTextMapHash', 0)
            desc_hash = main_quest.get('descTextMapHash', 0)
            
            quest_title = self.get_text(title_hash)
            quest_desc = self.get_text(desc_hash)
            
            print(f"  Quest {quest_id}: {quest_title}")
            
            # Try CodexQuest first (for newer chapters like Fontaine)
            dialogues = self.extract_from_codexquest(quest_id)
            extraction_method = "CodexQuest"
            
            # Fallback to DialogExcelConfigData (for older chapters)
            if dialogues is None:
                dialogues = self.extract_from_dialog_tree(quest_id)
                extraction_method = "DialogTree"
            
            if dialogues:
                print(f"    Extracted {len(dialogues)} dialogues ({extraction_method})")
                
                chapter_output.append("─" * 60)
                chapter_output.append(f"【主线任务】{quest_title} (ID: {quest_id})")
                if quest_desc:
                    chapter_output.append(f"任务描述：{quest_desc}")
                chapter_output.append("─" * 60)
                chapter_output.append("")
                
                for dlg in dialogues:
                    speaker = dlg.get('speaker', '未知')
                    text = dlg.get('text', '')
                    if text:
                        chapter_output.append(f"{speaker}：{text}")
                
                chapter_output.append("")
            else:
                print(f"    No dialogues extracted")
        
        return "\n".join(chapter_output) if len(chapter_output) > 7 else None
    
    def extract_all(self, output_dir='output_v2', chapters=None, merge_all=True, write_text=True, validation_only=False, sample_count=20, seed=None):
        """Extract all Archon Quest dialogues"""
        output_path = Path(output_dir)
        output_path.mkdir(exist_ok=True)

        archon_chapters = self.get_archon_chapters()
        if chapters:
            chapter_set = {int(c) for c in chapters}
            archon_chapters = [ch for ch in archon_chapters if ch.get('id') in chapter_set]

        print(f"Found {len(archon_chapters)} Archon Quest chapters")

        all_content = []
        chapter_count = 0
        coverage = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "output_dir": str(output_path),
            "summary": {
                "total_chapters": 0,
                "total_dialogues": 0,
                "total_missing_texts": 0
            },
            "chapters": []
        }
        sample_lines = []

        rng = random.Random(seed) if seed is not None else random

        for chapter in archon_chapters:
            chapter_id = chapter.get('id', 0)
            content = self.extract_chapter(chapter)

            if not content:
                continue

            lines = [line for line in content.split("\n") if line.strip()]
            dialogue_lines = [line for line in lines if "：" in line]
            missing_count = sum(1 for line in lines if "[Missing:" in line)

            coverage["chapters"].append({
                "id": str(chapter_id),
                "dialogues": len(dialogue_lines),
                "missing_texts": missing_count
            })
            coverage["summary"]["total_chapters"] += 1
            coverage["summary"]["total_dialogues"] += len(dialogue_lines)
            coverage["summary"]["total_missing_texts"] += missing_count

            if write_text and not validation_only:
                chapter_file = output_path / f"Chapter_{chapter_id}.txt"
                with open(chapter_file, 'w', encoding='utf-8') as f:
                    f.write(content)

                all_content.append(content)
                chapter_count += 1

            if dialogue_lines and sample_count > 0:
                for idx, line in enumerate(dialogue_lines):
                    if len(sample_lines) < sample_count:
                        sample_lines.append({
                            "chapter_id": str(chapter_id),
                            "line_index": idx,
                            "text": line
                        })
                    else:
                        if rng.random() < 0.1:
                            replace_idx = rng.randrange(sample_count)
                            sample_lines[replace_idx] = {
                                "chapter_id": str(chapter_id),
                                "line_index": idx,
                                "text": line
                            }

        coverage_report = output_path / "coverage_report.json"
        with open(coverage_report, 'w', encoding='utf-8') as f:
            json.dump(coverage, f, ensure_ascii=False, indent=2)

        validation_samples = output_path / "validation_samples.jsonl"
        with open(validation_samples, 'w', encoding='utf-8') as f:
            for item in sample_lines:
                f.write(json.dumps(item, ensure_ascii=False) + "\n")

        if write_text and merge_all and all_content and not validation_only:
            all_in_one = output_path / "ArchonQuest_CHS_AllInOne.txt"
            with open(all_in_one, 'w', encoding='utf-8') as f:
                f.write("\n\n".join(all_content))

            print(f"\n{'='*60}")
            print(f"Extraction complete!")
            print(f"Total chapters: {chapter_count}")
            print(f"Output directory: {output_path}")
            print(f"All-in-one file: {all_in_one}")
            print(f"Coverage report: {coverage_report}")
            print(f"Validation samples: {validation_samples}")
            print(f"{'='*60}")
        else:
            print(f"\n{'='*60}")
            print(f"Validation complete!")
            print(f"Total chapters: {coverage['summary']['total_chapters']}")
            print(f"Output directory: {output_path}")
            print(f"Coverage report: {coverage_report}")
            print(f"Validation samples: {validation_samples}")
            print(f"{'='*60}")


def parse_args():
    parser = argparse.ArgumentParser(description="Genshin Impact Archon Quest Dialogue Extractor")
    parser.add_argument("--data-dir", default="GenshinScripts/data", help="Path to extracted Excel/TextMap data")
    parser.add_argument("--repo-dir", default="AnimeGameData", help="Path to AnimeGameData repo (CodexQuest)")
    parser.add_argument("--output-dir", default="output", help="Output directory")
    parser.add_argument("--chapters", default="", help="Comma-separated chapter IDs to extract")
    parser.add_argument("--merge-all", action="store_true", help="Write merged all-in-one text output")
    parser.add_argument("--no-text-output", action="store_true", help="Skip writing full text outputs")
    parser.add_argument("--validation-only", action="store_true", help="Only generate coverage/sample validation outputs")
    parser.add_argument("--lang", default="CHS", help="TextMap language code, e.g. CHS/CHT/EN")
    parser.add_argument("--sample-count", type=int, default=20, help="Number of validation samples to retain")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for validation sampling")
    return parser.parse_args()


if __name__ == '__main__':
    args = parse_args()
    chapters = [c.strip() for c in args.chapters.split(",") if c.strip()] if args.chapters else None
    extractor = ArchonQuestExtractorV2(
        data_dir=args.data_dir,
        repo_dir=args.repo_dir,
        textmap_lang=args.lang
    )
    extractor.extract_all(
        output_dir=args.output_dir,
        chapters=chapters,
        merge_all=args.merge_all,
        write_text=not args.no_text_output,
        validation_only=args.validation_only,
        sample_count=args.sample_count,
        seed=args.seed
    )
