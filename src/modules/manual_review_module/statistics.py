"""
Statistics and Reporting Module

Provides comprehensive statistics and reporting for table review operations.
"""

import json
import csv
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass, asdict
import statistics as stats

from src.modules.manual_review_module.correction_manager import CorrectionManager
from src.modules.manual_review_module.table_extractor import LawTableExtractor


@dataclass
class TableStatistics:
    """Statistics for table processing."""
    total_tables: int
    confirmed_tables: int
    rejected_tables: int
    edited_tables: int
    merged_tables: int
    tables_with_errors: int
    avg_tables_per_law: float
    
    @property
    def processed_tables(self) -> int:
        return self.confirmed_tables + self.rejected_tables + self.edited_tables + self.merged_tables


@dataclass
class LawStatistics:
    """Statistics for law processing."""
    total_laws: int
    completed_laws: int
    laws_with_tables: int
    laws_without_tables: int
    laws_with_errors: int
    completion_rate: float
    avg_processing_time: Optional[float] = None


@dataclass
class ReviewReport:
    """Comprehensive review report."""
    report_id: str
    generated_at: str
    folder_name: str
    law_stats: LawStatistics
    table_stats: TableStatistics
    detailed_results: List[Dict[str, Any]]
    processing_summary: Dict[str, Any]
    time_analysis: Dict[str, Any]


class StatisticsCollector:
    """Collects and analyzes statistics from table review operations."""
    
    def __init__(self, base_path: str = "data/zhlex"):
        self.base_path = Path(base_path)
        self.correction_manager = CorrectionManager(str(self.base_path))
        self.table_extractor = LawTableExtractor()
        self.logger = logging.getLogger(__name__)
    
    def generate_folder_report(self, folder_name: str) -> ReviewReport:
        """
        Generate a comprehensive report for a folder.
        
        Args:
            folder_name: Name of the folder to analyze
            
        Returns:
            Comprehensive review report
        """
        folder_path = self.base_path / folder_name
        
        if not folder_path.exists():
            raise ValueError(f"Folder does not exist: {folder_path}")
        
        # Get all laws in folder
        all_laws = self.table_extractor.get_laws_in_folder(str(folder_path))
        
        # Collect detailed data for each law
        detailed_results = []
        table_counts = []
        processing_times = []
        
        total_tables = 0
        tables_by_status = {"confirmed": 0, "rejected": 0, "edited": 0, "merged": 0, "errors": 0}
        laws_with_tables = 0
        laws_with_errors = 0
        completed_laws = 0
        
        for law_id in all_laws:
            law_result = self._analyze_single_law(law_id, folder_name, str(folder_path))
            detailed_results.append(law_result)
            
            # Aggregate statistics
            if law_result["completed"]:
                completed_laws += 1
            
            if law_result["table_count"] > 0:
                laws_with_tables += 1
                table_counts.append(law_result["table_count"])
                total_tables += law_result["table_count"]
                
                # Count tables by status
                for status, count in law_result["tables_by_status"].items():
                    if status in tables_by_status:
                        tables_by_status[status] += count
            
            if law_result["has_errors"]:
                laws_with_errors += 1
            
            if law_result["processing_time"]:
                processing_times.append(law_result["processing_time"])
        
        # Calculate statistics
        law_stats = LawStatistics(
            total_laws=len(all_laws),
            completed_laws=completed_laws,
            laws_with_tables=laws_with_tables,
            laws_without_tables=len(all_laws) - laws_with_tables,
            laws_with_errors=laws_with_errors,
            completion_rate=(completed_laws / len(all_laws)) * 100 if all_laws else 0.0,
            avg_processing_time=stats.mean(processing_times) if processing_times else None
        )
        
        table_stats = TableStatistics(
            total_tables=total_tables,
            confirmed_tables=tables_by_status["confirmed"],
            rejected_tables=tables_by_status["rejected"],
            edited_tables=tables_by_status["edited"],
            merged_tables=tables_by_status["merged"],
            tables_with_errors=tables_by_status["errors"],
            avg_tables_per_law=stats.mean(table_counts) if table_counts else 0.0
        )
        
        # Processing summary
        processing_summary = {
            "efficiency_metrics": {
                "laws_per_hour": 3600 / law_stats.avg_processing_time if law_stats.avg_processing_time else None,
                "tables_per_hour": 3600 * (total_tables / sum(processing_times)) if processing_times else None,
                "error_rate": (laws_with_errors / len(all_laws)) * 100 if all_laws else 0.0
            },
            "table_distribution": {
                "laws_with_1_table": sum(1 for count in table_counts if count == 1),
                "laws_with_2_5_tables": sum(1 for count in table_counts if 2 <= count <= 5),
                "laws_with_6_plus_tables": sum(1 for count in table_counts if count > 5),
                "max_tables_in_single_law": max(table_counts) if table_counts else 0,
                "median_tables_per_law": stats.median(table_counts) if table_counts else 0
            }
        }
        
        # Time analysis
        time_analysis = {}
        if processing_times:
            time_analysis = {
                "total_processing_time": sum(processing_times),
                "min_processing_time": min(processing_times),
                "max_processing_time": max(processing_times),
                "median_processing_time": stats.median(processing_times),
                "std_dev_processing_time": stats.stdev(processing_times) if len(processing_times) > 1 else 0
            }
        
        return ReviewReport(
            report_id=f"report_{folder_name}_{int(datetime.now().timestamp())}",
            generated_at=datetime.now().isoformat(),
            folder_name=folder_name,
            law_stats=law_stats,
            table_stats=table_stats,
            detailed_results=detailed_results,
            processing_summary=processing_summary,
            time_analysis=time_analysis
        )
    
    def _analyze_single_law(self, law_id: str, folder_name: str, folder_path: str) -> Dict[str, Any]:
        """
        Analyze a single law for statistics.
        
        Args:
            law_id: Law identifier
            folder_name: Folder name for corrections
            folder_path: Full path to folder
            
        Returns:
            Dictionary with law analysis results
        """
        result = {
            "law_id": law_id,
            "completed": False,
            "table_count": 0,
            "tables_by_status": {"confirmed": 0, "rejected": 0, "edited": 0, "merged": 0, "errors": 0},
            "has_errors": False,
            "processing_time": None,
            "correction_file_size": 0,
            "last_modified": None,
            "unique_table_hashes": []
        }
        
        try:
            # Check if law is completed
            result["completed"] = self.correction_manager.is_law_completed(law_id, folder_name)
            
            # Get corrections if available
            corrections = self.correction_manager.get_corrections(law_id, folder_name)
            
            if corrections:
                result["last_modified"] = corrections.get("reviewed_at")
                
                # Analyze tables
                tables = corrections.get("tables", {})
                result["table_count"] = len(tables)
                result["unique_table_hashes"] = list(tables.keys())
                
                for table_hash, table_data in tables.items():
                    status = table_data.get("status", "unknown")
                    if status in result["tables_by_status"]:
                        result["tables_by_status"][status] += 1
                    else:
                        result["tables_by_status"]["errors"] += 1
                
                # Calculate processing time estimate (if timestamps are available)
                if "reviewed_at" in corrections:
                    try:
                        review_time = datetime.fromisoformat(corrections["reviewed_at"])
                        # Estimate based on table count (rough heuristic)
                        result["processing_time"] = len(tables) * 30  # 30 seconds per table estimate
                    except Exception:
                        pass
                
                # Get correction file size
                correction_file = self.correction_manager.get_correction_file_path(law_id, folder_name)
                if correction_file.exists():
                    result["correction_file_size"] = correction_file.stat().st_size
            else:
                # Try to extract tables from original data to see what's available
                try:
                    unique_tables = self.table_extractor.extract_unique_tables_from_law(law_id, folder_path)
                    result["table_count"] = len(unique_tables)
                    result["unique_table_hashes"] = list(unique_tables.keys())
                except Exception as e:
                    result["has_errors"] = True
                    self.logger.error(f"Error extracting tables from law {law_id}: {e}")
        
        except Exception as e:
            result["has_errors"] = True
            self.logger.error(f"Error analyzing law {law_id}: {e}")
        
        return result


class ReportExporter:
    """Exports reports in various formats."""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
    
    def export_json(self, report: ReviewReport, output_path: str) -> None:
        """Export report as JSON."""
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
            self.logger.info(f"JSON report exported to: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to export JSON report: {e}")
            raise
    
    def export_csv(self, report: ReviewReport, output_path: str) -> None:
        """Export detailed results as CSV."""
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                if not report.detailed_results:
                    return
                
                fieldnames = report.detailed_results[0].keys()
                writer = csv.DictWriter(f, fieldnames=fieldnames)
                writer.writeheader()
                
                for result in report.detailed_results:
                    # Flatten nested dictionaries
                    flat_result = {}
                    for key, value in result.items():
                        if isinstance(value, dict):
                            for sub_key, sub_value in value.items():
                                flat_result[f"{key}_{sub_key}"] = sub_value
                        elif isinstance(value, list):
                            flat_result[key] = ', '.join(map(str, value))
                        else:
                            flat_result[key] = value
                    writer.writerow(flat_result)
            
            self.logger.info(f"CSV report exported to: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to export CSV report: {e}")
            raise
    
    def export_html(self, report: ReviewReport, output_path: str) -> None:
        """Export report as HTML."""
        html_content = self._generate_html_report(report)
        
        try:
            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)
            self.logger.info(f"HTML report exported to: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to export HTML report: {e}")
            raise
    
    def _generate_html_report(self, report: ReviewReport) -> str:
        """Generate HTML content for the report."""
        html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Table Review Report - {report.folder_name}</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 20px; }}
        .header {{ background-color: #f5f5f5; padding: 20px; border-radius: 5px; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 20px; margin: 20px 0; }}
        .stat-card {{ background-color: #fff; border: 1px solid #ddd; padding: 15px; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        .stat-number {{ font-size: 2em; font-weight: bold; color: #2c3e50; }}
        .stat-label {{ color: #7f8c8d; text-transform: uppercase; font-size: 0.9em; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
        th {{ background-color: #f5f5f5; }}
        .success {{ color: #27ae60; }}
        .warning {{ color: #f39c12; }}
        .error {{ color: #e74c3c; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Table Review Report</h1>
        <p><strong>Folder:</strong> {report.folder_name}</p>
        <p><strong>Generated:</strong> {report.generated_at}</p>
        <p><strong>Report ID:</strong> {report.report_id}</p>
    </div>
    
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number">{report.law_stats.total_laws}</div>
            <div class="stat-label">Total Laws</div>
        </div>
        <div class="stat-card">
            <div class="stat-number success">{report.law_stats.completed_laws}</div>
            <div class="stat-label">Completed Laws</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{report.table_stats.total_tables}</div>
            <div class="stat-label">Total Tables</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{report.law_stats.completion_rate:.1f}%</div>
            <div class="stat-label">Completion Rate</div>
        </div>
    </div>
    
    <h2>Table Processing Summary</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <div class="stat-number success">{report.table_stats.confirmed_tables}</div>
            <div class="stat-label">Confirmed Tables</div>
        </div>
        <div class="stat-card">
            <div class="stat-number warning">{report.table_stats.rejected_tables}</div>
            <div class="stat-label">Rejected Tables</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{report.table_stats.edited_tables}</div>
            <div class="stat-label">Edited Tables</div>
        </div>
        <div class="stat-card">
            <div class="stat-number">{report.table_stats.merged_tables}</div>
            <div class="stat-label">Merged Tables</div>
        </div>
    </div>
    
    <h2>Detailed Results</h2>
    <table>
        <thead>
            <tr>
                <th>Law ID</th>
                <th>Status</th>
                <th>Tables</th>
                <th>Confirmed</th>
                <th>Rejected</th>
                <th>Edited</th>
                <th>Merged</th>
                <th>Errors</th>
            </tr>
        </thead>
        <tbody>
"""
        
        for result in report.detailed_results:
            status_class = "success" if result["completed"] else "warning"
            status_text = "✅ Completed" if result["completed"] else "⏳ Pending"
            
            html += f"""
            <tr>
                <td>{result["law_id"]}</td>
                <td class="{status_class}">{status_text}</td>
                <td>{result["table_count"]}</td>
                <td>{result["tables_by_status"]["confirmed"]}</td>
                <td>{result["tables_by_status"]["rejected"]}</td>
                <td>{result["tables_by_status"]["edited"]}</td>
                <td>{result["tables_by_status"]["merged"]}</td>
                <td class="error">{result["tables_by_status"]["errors"]}</td>
            </tr>
            """
        
        html += """
        </tbody>
    </table>
</body>
</html>
"""
        return html


def generate_comprehensive_report(folder_name: str, output_dir: str = "reports",
                                base_path: str = "data/zhlex") -> Dict[str, str]:
    """
    Generate comprehensive reports in all formats.
    
    Args:
        folder_name: Name of the folder to analyze
        output_dir: Directory to save reports
        base_path: Base path for data
        
    Returns:
        Dictionary mapping format to output file path
    """
    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(exist_ok=True)
    
    # Generate report
    collector = StatisticsCollector(base_path)
    report = collector.generate_folder_report(folder_name)
    
    # Export in all formats
    exporter = ReportExporter()
    output_files = {}
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_filename = f"table_review_{folder_name}_{timestamp}"
    
    # JSON
    json_path = output_path / f"{base_filename}.json"
    exporter.export_json(report, str(json_path))
    output_files["json"] = str(json_path)
    
    # CSV
    csv_path = output_path / f"{base_filename}.csv"
    exporter.export_csv(report, str(csv_path))
    output_files["csv"] = str(csv_path)
    
    # HTML
    html_path = output_path / f"{base_filename}.html"
    exporter.export_html(report, str(html_path))
    output_files["html"] = str(html_path)
    
    return output_files