import { Train } from '../shared/types';

interface TrainBoxProps {
  train: Train;
  onClick: (train: Train) => void;
  type: 'dep' | 'arr';
}

const getTrainClass = (type: string) => {
  const t = type.toLowerCase();
  if (t.includes('ktx-산천') || t.includes('a산천') || t.includes('b산천') || t.includes('산천')) return 'sancheon';
  if (t.includes('ktx-이음') || t.includes('이음')) return 'eum';
  if (t.includes('ktx-청룡') || t.includes('청룡')) return 'cheongryong';
  if (t.includes('ktx')) return 'ktx';
  if (t.includes('srt')) return 'srt';
  if (t.includes('itx-청춘') || t.includes('i청춘')) return 'itx-cheongchun';
  if (t.includes('itx-마음') || t.includes('마음')) return 'itx-maum';
  if (t.includes('itx-새마을') || t.includes('i새마을') || t.includes('새마을')) return 'itx-saemaul';
  if (t.includes('무궁화')) return 'mugunghwa';
  if (t.includes('누리로')) return 'nuriro';
  return '';
};

const formatTrainNo = (trainNo: string) => {
  const val = parseInt(trainNo.replace(/[^0-9]/g, ''), 10);
  if (isNaN(val)) return trainNo;
  const s = String(val);
  return s.length <= 3 ? s.padStart(3, '0') : s.padStart(4, '0');
};

const TrainBox = ({ train, onClick, type }: TrainBoxProps) => {
  const time = type === 'dep' ? train.depTime : train.arrTime;
  const minute = time.split(':')[1];

  return (
    <div 
      className={`train-box ${getTrainClass(train.type)}`} 
      onClick={() => onClick(train)}
    >
      <span className="minute">
        {minute}
        <sup className="train-marker">
          {train.isOriginStation && <span className="marker-origin">●</span>}
          {train.viaRouteMarker && <span className="marker-via">{train.viaRouteMarker}</span>}
        </sup>
      </span>
      <span className="train-info">{train.type}#{formatTrainNo(train.trainNo)}</span>
      <span className="train-dest">{train.destination}</span>
    </div>
  );
};

export default TrainBox;
