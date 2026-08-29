import os
import requests
import pandas as pd
from dotenv import load_dotenv
import time

# .env 파일 로드 (프로젝트 루트의 .env)
load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))

# API 키 설정
KEY = os.getenv('TRAIN_TIME_API_KEY_4') or os.getenv('TRAIN_TIME_API_KEY_3')

# API 엔드포인트
RESULT_URL = "https://apis.data.go.kr/B551457/run/v2/travelerTrainRunInfo2"
PLAN_URL = "https://apis.data.go.kr/B551457/run/v2/travelerTrainRunPlan2"

def format_time(t_str):
    """YYYY-MM-DD HH:MM:SS.0 -> HH:MM:SS"""
    t_str = str(t_str).strip()
    if t_str and len(t_str) >= 19:
        return t_str[11:19]
    return "-"

def get_station_data(date_str, stn_nm):
    """특정 역의 모든 열차 실적(Result)과 계획(Plan)을 가져와 비교 (운전정차 포함)"""
    print(f"\n[{date_str}] '{stn_nm}'역 데이터 조회 중 (운전정차 포함)...")

    # 1. 실적(Result) 조회
    res_params = {
        'serviceKey': KEY, 'returnType': 'JSON', 'pageNo': 1, 'numOfRows': 1000,
        'cond[run_ymd::GTE]': date_str, 'cond[run_ymd::LTE]': date_str,
        'cond[stn_nm::EQ]': stn_nm
    }
    
    result_data = {}
    try:
        resp = requests.get(RESULT_URL, params=res_params, timeout=20)
        if resp.status_code == 200:
            items = resp.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            for it in items:
                trn_no = it.get('trn_no', '').zfill(5)
                # 정차 구분 코드 확인 (11: 여객, 12: 운전정차 등)
                stop_nm = it.get('stop_se_nm', '알수없음')
                result_data[trn_no] = {
                    '실적_도착': format_time(it.get('trn_arvl_dt')),
                    '실적_출발': format_time(it.get('trn_dptre_dt')),
                    '정차구분': stop_nm
                }
    except Exception as e:
        print(f"  ⚠️ 실적 조회 오류: {e}")

    if not result_data:
        print(f"  ❌ '{stn_nm}'역의 실적 데이터를 찾을 수 없습니다. (운행 전, 기간 만료 혹은 역명 오류)")
        return

    # 2. 계획(Plan) 조회
    plan_params = {
        'serviceKey': KEY, 'returnType': 'JSON', 'pageNo': 1, 'numOfRows': 2000,
        'cond[run_ymd::GTE]': date_str, 'cond[run_ymd::LTE]': date_str
    }
    
    plan_data = {}
    print(f"  계획 데이터 매칭 중 (실적 확인된 {len(result_data)}대 기준)...")
    try:
        resp = requests.get(PLAN_URL, params=plan_params, timeout=20)
        if resp.status_code == 200:
            items = resp.json().get('response', {}).get('body', {}).get('items', {}).get('item', [])
            if isinstance(items, dict): items = [items]
            for it in items:
                if it.get('stn_nm') == stn_nm:
                    trn_no = it.get('trn_no', '').zfill(5)
                    plan_data[trn_no] = {
                        '계획_도착': format_time(it.get('trn_arvl_dt')),
                        '계획_출발': format_time(it.get('trn_dptre_dt'))
                    }
    except Exception as e:
        print(f"  ⚠️ 계획 조회 오류: {e}")

    # 3. 데이터 병합 및 출력
    final_rows = []
    all_trn_nos = sorted(list(set(result_data.keys()) | set(plan_data.keys())))
    
    for tn in all_trn_nos:
        p = plan_data.get(tn, {'계획_도착': '-', '계획_출발': '-'})
        r = result_data.get(tn, {'실적_도착': '-', '실적_출발': '-', '정차구분': '미확인'})
        
        final_rows.append({
            '열차번호': tn,
            '정차구분': r['정차구분'],
            '계획_도착': p['계획_도착'],
            '실적_도착': r['실적_도착'],
            '계획_출발': p['계획_출발'],
            '실적_출발': r['실적_출발']
        })
    
    df = pd.DataFrame(final_rows)
    if not df.empty:
        # 출력 폭 조정
        pd.set_option('display.max_rows', None)
        pd.set_option('display.width', 1000)
        
        print("\n" + "="*85)
        print(f"  [{stn_nm}역] 열차별 계획 vs 실적 (날짜: {date_str}, 운전정차 포함)")
        print("="*85)
        print(df.to_string(index=False))
        print("="*85)
        
        filename = f"station_{stn_nm}_{date_str}_full.csv"
        df.to_csv(filename, index=False, encoding='utf-8-sig')
        print(f"✅ 상세 결과가 '{filename}'으로 저장되었습니다.")
        
        # 운전정차 통계 요약
        stop_counts = df['정차구분'].value_counts()
        print("\n[정차 유형 요약]")
        for nm, cnt in stop_counts.items():
            print(f" - {nm}: {cnt}대")
    else:
        print("  ℹ️ 표시할 데이터가 없습니다.")

def main():
    print("========================================")
    print("   역별 열차 통합 조회 (운전정차 포함)  ")
    print("========================================")
    
    stn_nm = input("조회할 역명 (예: 서울, 대전, 신창원): ").strip()
    date_input = input("조회 날짜 (YYYYMMDD, 엔터 시 오늘): ").strip()
    
    if not date_input:
        date_input = time.strftime('%Y%m%d')
    
    if stn_nm:
        get_station_data(date_input, stn_nm)
    else:
        print("❌ 역명을 입력해야 합니다.")

if __name__ == "__main__":
    main()
