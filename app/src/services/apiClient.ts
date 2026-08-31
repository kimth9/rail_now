import { TimetableRequest, TimetableResponse, TrainStop } from '../shared/types';

const API_BASE = '/api';

export const apiClient = {
  async searchStations(query: string): Promise<string[]> {
    const res = await fetch(`${API_BASE}/stations?q=${encodeURIComponent(query)}`);
    if (!res.ok) throw new Error('역 검색 실패');
    return res.json();
  },

  async fetchTimetable(params: TimetableRequest): Promise<TimetableResponse> {
    const { depStation, arrStation, date } = params;
    const res = await fetch(`${API_BASE}/timetable?dep=${encodeURIComponent(depStation)}&arr=${encodeURIComponent(arrStation)}&date=${date}`);
    if (!res.ok) {
      const err = await res.json();
      throw new Error(err.error || '시간표 조회 실패');
    }
    return res.json();
  },

  async fetchTrainStops(trainNo: string, date: string): Promise<TrainStop[]> {
    const res = await fetch(`${API_BASE}/stops?trainNo=${trainNo}&date=${date}`);
    if (!res.ok) throw new Error('정차역 정보 조회 실패');
    return res.json();
  }
};
