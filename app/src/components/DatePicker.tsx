import React, { useState, useEffect, useRef } from 'react';

interface DatePickerProps {
  value: string; // YYYYMMDD
  onChange: (date: string) => void;
}

const DatePicker: React.FC<DatePickerProps> = ({ value, onChange }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [currentMonth, setCurrentMonth] = useState(new Date());
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (value && value.length === 8) {
      const year = parseInt(value.substring(0, 4));
      const month = parseInt(value.substring(4, 6)) - 1;
      const day = parseInt(value.substring(6, 8));
      setCurrentMonth(new Date(year, month, day));
    }
  }, [value]);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const getDaysInMonth = (year: number, month: number) => {
    return new Date(year, month + 1, 0).getDate();
  };

  const getFirstDayOfMonth = (year: number, month: number) => {
    return new Date(year, month, 1).getDay();
  };

  const formatDate = (date: Date) => {
    const year = date.getFullYear();
    const month = String(date.getMonth() + 1).padStart(2, '0');
    const day = String(date.getDate()).padStart(2, '0');
    return `${year}${month}${day}`;
  };

  const handlePrevMonth = (e: React.MouseEvent) => {
    e.preventDefault();
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() - 1, 1));
  };

  const handleNextMonth = (e: React.MouseEvent) => {
    e.preventDefault();
    setCurrentMonth(new Date(currentMonth.getFullYear(), currentMonth.getMonth() + 1, 1));
  };

  const handleDateClick = (day: number) => {
    const newDate = new Date(currentMonth.getFullYear(), currentMonth.getMonth(), day);
    onChange(formatDate(newDate));
    setIsOpen(false);
  };

  const renderCalendar = () => {
    const year = currentMonth.getFullYear();
    const month = currentMonth.getMonth();
    const daysInMonth = getDaysInMonth(year, month);
    const firstDay = getFirstDayOfMonth(year, month);
    
    const days = [];
    for (let i = 0; i < firstDay; i++) {
      days.push(<div key={`empty-${i}`} className="calendar-day empty"></div>);
    }

    for (let day = 1; day <= daysInMonth; day++) {
      const dateStr = formatDate(new Date(year, month, day));
      const isSelected = dateStr === value;
      const isToday = formatDate(new Date()) === dateStr;

      days.push(
        <div 
          key={day} 
          className={`calendar-day ${isSelected ? 'selected' : ''} ${isToday ? 'today' : ''}`}
          onClick={() => handleDateClick(day)}
        >
          {day}
        </div>
      );
    }

    return days;
  };

  const getDayOfWeek = (ymd: string) => {
    if (ymd.length !== 8) return '';
    const year = parseInt(ymd.substring(0, 4));
    const month = parseInt(ymd.substring(4, 6)) - 1;
    const day = parseInt(ymd.substring(6, 8));
    const date = new Date(year, month, day);
    const days = ['일', '월', '화', '수', '목', '금', '토'];
    return days[date.getDay()];
  };

  const displayValue = value.length === 8 
    ? `${value.substring(0, 4)}/${value.substring(4, 6)}/${value.substring(6, 8)}(${getDayOfWeek(value)})`
    : value;

  return (
    <div className="datepicker-container" ref={containerRef}>
      <label>조회 날짜</label>
      <div className="datepicker-input-wrapper" onClick={() => setIsOpen(!isOpen)}>
        <input 
          type="text" 
          value={displayValue} 
          readOnly 
          placeholder="날짜를 선택하세요"
        />
        <span className="calendar-icon">📅</span>
      </div>

      {isOpen && (
        <div className="calendar-dropdown">
          <div className="calendar-header">
            <button onClick={handlePrevMonth}>&lt;</button>
            <span>{currentMonth.getFullYear()}년 {currentMonth.getMonth() + 1}월</span>
            <button onClick={handleNextMonth}>&gt;</button>
          </div>
          <div className="calendar-weekdays">
            <div className="weekday sun">일</div>
            <div className="weekday">월</div>
            <div className="weekday">화</div>
            <div className="weekday">수</div>
            <div className="weekday">목</div>
            <div className="weekday">금</div>
            <div className="weekday sat">토</div>
          </div>
          <div className="calendar-grid">
            {renderCalendar()}
          </div>
        </div>
      )}
    </div>
  );
};

export default DatePicker;
