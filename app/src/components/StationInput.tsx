import React, { useState, useEffect, useRef } from 'react';
import { apiClient } from '../services/apiClient';

interface StationInputProps {
  label: string;
  value: string;
  onChange: (val: string) => void;
  placeholder: string;
}

const StationInput = ({ label, value, onChange, placeholder }: StationInputProps) => {
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const wrapperRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (wrapperRef.current && !wrapperRef.current.contains(event.target as Node)) {
        setShowSuggestions(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleInputChange = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const query = e.target.value;
    onChange(query);
    if (query) {
      try {
        const results = await apiClient.searchStations(query);
        setSuggestions(results.slice(0, 10));
        setShowSuggestions(true);
      } catch (err) {
        console.error(err);
      }
    } else {
      setSuggestions([]);
      setShowSuggestions(false);
    }
  };

  const handleSelect = (station: string) => {
    onChange(station);
    setShowSuggestions(false);
  };

  return (
    <div className="input-group station-input-wrapper" ref={wrapperRef}>
      <label>{label}</label>
      <input 
        value={value} 
        onChange={handleInputChange} 
        onFocus={() => value && setShowSuggestions(true)}
        placeholder={placeholder} 
      />
      {showSuggestions && suggestions.length > 0 && (
        <ul className="suggestions-list">
          {suggestions.map((s, i) => (
            <li key={i} onClick={() => handleSelect(s)}>{s}</li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default StationInput;
