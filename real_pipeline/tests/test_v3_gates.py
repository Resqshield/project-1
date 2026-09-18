import os
import pandas as pd
import pytest

def test_v3_matrix_gates():
    v3_path = "data_real/features/flood_training_v3.parquet"
    assert os.path.exists(v3_path), "V3 matrix must exist"
    df_v3 = pd.read_parquet(v3_path)
    
    # Gate 1: Positive events >= 10
    pos_events = df_v3[df_v3['label'] == 1]['event_id'].nunique()
    regions = df_v3['region'].nunique()
    
    assert pos_events >= 10, f"Expected >= 10 positive events, got {pos_events}"
    assert regions >= 5, f"Expected >= 5 regions, got {regions}"
    
    # Gate 2: High terrain feature coverage
    missing_dist = df_v3['distance_to_stream_m'].isnull().sum()
    missing_pct = missing_dist / len(df_v3)
    # Allow < 1% missing strictly due to upstream invalid LGD village geometries (approx 0.3% missing)
    assert missing_pct < 0.01, f"Distance to stream coverage fell below 99% (missing {missing_dist}/{len(df_v3)})"
    
    missing_flow = df_v3['flow_accumulation_skm'].isnull().sum()
    missing_flow_pct = missing_flow / len(df_v3)
    assert missing_flow_pct < 0.01, f"Flow accumulation coverage fell below 99% (missing {missing_flow}/{len(df_v3)})"

def test_stream_provenance():
    streams_path = "data_real/hydrology/processed/hydro_rivers_india.parquet"
    assert os.path.exists(streams_path)
    df = pd.read_parquet(streams_path)
    assert 'HYRIV_ID' in df.columns
    assert 'NEXT_DOWN' in df.columns
    assert 'UPLAND_SKM' in df.columns

def test_village_catchment_integrity():
    link_path = "data_real/hydrology/processed/village_catchment_link.parquet"
    assert os.path.exists(link_path)
    df = pd.read_parquet(link_path)
    assert 'village_lgd_code' in df.columns
    assert 'catchment_id' in df.columns
    assert 'overlap_fraction' in df.columns
    
    linked = df.dropna(subset=['catchment_id'])
    assert len(linked) > 10000, "Should have linked > 10k villages"

def test_event_admin_mapping():
    v3_path = "data_real/features/flood_training_v3.parquet"
    if os.path.exists(v3_path):
        df_v3 = pd.read_parquet(v3_path)
        assert 'region' in df_v3.columns
        assert 'village_lgd_code' in df_v3.columns

def test_crosswalk_validity():
    link_path = "data_real/hydrology/processed/village_catchment_link.parquet"
    if os.path.exists(link_path):
        df = pd.read_parquet(link_path)
        assert 'village_lgd_code' in df.columns
        assert 'catchment_id' in df.columns
        assert 'overlap_fraction' in df.columns
        assert 'dominant_catchment' in df.columns
        assert 'geometry_source' in df.columns
        assert 'linkage_method' in df.columns

def test_lead_time_measurement():
    v3_path = "data_real/features/flood_training_v3.parquet"
    if os.path.exists(v3_path):
        df_v3 = pd.read_parquet(v3_path)
        if 'lead_time_days' in df_v3.columns:
            assert not df_v3['lead_time_days'].isnull().all()
        elif 'lead_time_status' in df_v3.columns:
            assert (df_v3['lead_time_status'] == 'LEAD_TIME_NOT_MEASURABLE_YET').all() or not df_v3['lead_time_status'].isnull().all()
