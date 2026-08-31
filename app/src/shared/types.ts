export interface Station {
  name: string;
  id: string;
}

export interface TrainStop {
  station: string;
  arrTime: string; // HH:mm
  depTime: string; // HH:mm
  stopType?: string;
}

export interface Train {
  id: string;
  type: string;
  trainNo: string;
  destination: string;
  depTime: string; // HH:mm
  arrTime: string; // HH:mm
  originalType: string;
  viaRouteMarker?: string; // "수", "구", "서", "홍내", "홍외"
  isOriginStation?: boolean; // 당역 출발 마크 (●)
}

export interface TimetableRequest {
  depStation: string;
  arrStation: string;
  date: string; // YYYYMMDD
}

export interface TimetableResponse {
  trains: Train[];
}
