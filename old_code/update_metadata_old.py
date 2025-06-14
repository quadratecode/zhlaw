from src.modules.zhlex_module import update_metadata

# Update source metadata for all laws
processed_data = "data/zhlex/zhlex_data/zhlex_data_processed.json"
update_metadata.main("data/zhlex/zhlex_files", processed_data)
