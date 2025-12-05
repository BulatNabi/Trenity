import React, { useState, useEffect } from 'react';
import axios from 'axios';
import './App.css';

// В Docker используем относительный путь через nginx, иначе localhost
const API_URL = process.env.REACT_APP_API_URL ||
  (window.location.hostname === 'localhost' && window.location.port === '3000'
    ? 'http://localhost:8000'
    : '/api');

function App() {
  const [groupsBySocial, setGroupsBySocial] = useState([]);
  const [selectedAccounts, setSelectedAccounts] = useState(new Set());
  const [expandedSocials, setExpandedSocials] = useState(new Set());
  const [videoFile, setVideoFile] = useState(null);
  const [publishDate, setPublishDate] = useState('');
  const [publishTime, setPublishTime] = useState('');
  const [postText, setPostText] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [success, setSuccess] = useState(null);

  useEffect(() => {
    loadGroups();
  }, []);

  const loadGroups = async () => {
    try {
      setLoading(true);
      const response = await axios.get(`${API_URL}/groups/`);
      setGroupsBySocial(response.data);

      // По умолчанию выбираем все аккаунты
      const allAccounts = new Set();
      response.data.forEach(socialGroup => {
        socialGroup.groups.forEach(group => {
          allAccounts.add(JSON.stringify({
            id: group.id,
            social: group.social,
            type: group.type
          }));
        });
      });
      setSelectedAccounts(allAccounts);
    } catch (err) {
      setError('Ошибка загрузки групп: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const toggleSocial = (social) => {
    const newExpanded = new Set(expandedSocials);
    if (newExpanded.has(social)) {
      newExpanded.delete(social);
    } else {
      newExpanded.add(social);
    }
    setExpandedSocials(newExpanded);
  };

  const toggleAccount = (account) => {
    const accountKey = JSON.stringify(account);
    const newSelected = new Set(selectedAccounts);
    if (newSelected.has(accountKey)) {
      newSelected.delete(accountKey);
    } else {
      newSelected.add(accountKey);
    }
    setSelectedAccounts(newSelected);
  };

  const toggleAllInSocial = (social) => {
    const socialGroup = groupsBySocial.find(sg => sg.social === social);
    if (!socialGroup) return;

    const allSelected = socialGroup.groups.every(group => {
      const accountKey = JSON.stringify({
        id: group.id,
        social: group.social,
        type: group.type
      });
      return selectedAccounts.has(accountKey);
    });

    const newSelected = new Set(selectedAccounts);
    socialGroup.groups.forEach(group => {
      const accountKey = JSON.stringify({
        id: group.id,
        social: group.social,
        type: group.type
      });
      if (allSelected) {
        newSelected.delete(accountKey);
      } else {
        newSelected.add(accountKey);
      }
    });
    setSelectedAccounts(newSelected);
  };

  const getSocialName = (social) => {
    const names = {
      'vk': 'ВКонтакте',
      'io': 'Instagram',
      'gg': 'YouTube',
      'pi': 'Pinterest',
      'ok': 'Одноклассники',
      'fb': 'Facebook',
      'tg': 'Telegram',
      'tw': 'Twitter',
      'to': 'TikTok',
      'ry': 'RuTube'
    };
    return names[social] || social;
  };

  const handlePublish = async () => {
    if (!videoFile) {
      setError('Выберите видео файл');
      return;
    }

    if (!publishDate || !publishTime) {
      setError('Выберите дату и время публикации');
      return;
    }

    // Проверяем дату
    const selectedDateTime = new Date(`${publishDate}T${publishTime}`);
    const now = new Date();
    if (selectedDateTime < now) {
      setError('Дата публикации не может быть в прошлом');
      return;
    }

    if (selectedAccounts.size === 0) {
      setError('Выберите хотя бы один аккаунт');
      return;
    }

    try {
      setLoading(true);
      setError(null);
      setSuccess(null);

      // Формируем список выбранных аккаунтов
      const accountsList = Array.from(selectedAccounts).map(key => JSON.parse(key));

      // Формируем дату в ISO формате
      const publishDateTime = `${publishDate}T${publishTime}:00`;

      // Создаем FormData
      const formData = new FormData();
      formData.append('file', videoFile);
      formData.append('selected_accounts', JSON.stringify(accountsList));
      formData.append('publish_date', publishDateTime);
      if (postText && postText.trim()) {
        formData.append('post_text', postText.trim());
      }

      const response = await axios.post(`${API_URL}/publish/`, formData, {
        headers: {
          'Content-Type': 'multipart/form-data',
        },
      });

      setSuccess(`Успешно опубликовано! Аккаунтов: ${response.data.total_accounts}, Видео: ${response.data.total_videos}, Опубликовано: ${response.data.published}`);

      // Сбрасываем форму
      setVideoFile(null);
      setPublishDate('');
      setPublishTime('');
      setPostText('');
    } catch (err) {
      setError('Ошибка публикации: ' + (err.response?.data?.detail || err.message));
    } finally {
      setLoading(false);
    }
  };

  const getTodayDate = () => {
    const today = new Date();
    return today.toISOString().split('T')[0];
  };

  const getCurrentTime = () => {
    const now = new Date();
    const hours = String(now.getHours()).padStart(2, '0');
    const minutes = String(now.getMinutes()).padStart(2, '0');
    return `${hours}:${minutes}`;
  };

  return (
    <div className="App">
      <div className="container">
        <h1 className="title">TRENITY</h1>
        <p className="subtitle">Автопубликация видео в социальные сети</p>

        {error && (
          <div className="alert alert-error">
            {error}
          </div>
        )}

        {success && (
          <div className="alert alert-success">
            {success}
          </div>
        )}

        <div className="section">
          <h2 className="section-title">1. Загрузка видео</h2>
          <input
            type="file"
            accept="video/*"
            onChange={(e) => setVideoFile(e.target.files[0])}
            className="file-input"
          />
          {videoFile && (
            <p className="file-name">Выбрано: {videoFile.name}</p>
          )}
        </div>

        <div className="section">
          <h2 className="section-title">2. Дата и время публикации (МСК)</h2>
          <div className="date-time-inputs">
            <div className="date-picker-wrapper">
              <label>Выберите дату:</label>
              <div className="date-input-container">
                <input
                  type="date"
                  value={publishDate}
                  onChange={(e) => setPublishDate(e.target.value)}
                  min={getTodayDate()}
                  className="date-input"
                  id="date-picker"
                />
                <button
                  type="button"
                  onClick={() => document.getElementById('date-picker').showPicker?.() || document.getElementById('date-picker').click()}
                  className="calendar-icon-button"
                  title="Открыть календарь"
                >
                  📅
                </button>
              </div>
              {publishDate && (
                <p className="selected-date">
                  Выбрано: {new Date(publishDate + 'T00:00:00').toLocaleDateString('ru-RU', {
                    weekday: 'long',
                    year: 'numeric',
                    month: 'long',
                    day: 'numeric'
                  })}
                </p>
              )}
              {!publishDate && (
                <p className="text-hint" style={{ marginTop: '8px', fontSize: '12px' }}>
                  Нажмите на поле или иконку календаря для выбора даты
                </p>
              )}
            </div>
            <div>
              <label>Время (МСК):</label>
              <input
                type="time"
                value={publishTime}
                onChange={(e) => setPublishTime(e.target.value)}
                className="time-input"
              />
            </div>
          </div>
          <p className="text-hint">Время указывается в московском часовом поясе (МСК, UTC+3)</p>
        </div>

        <div className="section">
          <h2 className="section-title">3. Текст поста (опционально)</h2>
          <textarea
            value={postText}
            onChange={(e) => setPostText(e.target.value)}
            placeholder="Введите текст, который будет опубликован вместе с видео..."
            className="text-input"
            rows={5}
          />
          <p className="text-hint">Текст будет добавлен к каждому посту во всех выбранных аккаунтах</p>
        </div>

        <div className="section">
          <h2 className="section-title">4. Выбор аккаунтов</h2>
          <p className="accounts-info">
            Всего выбрано: {selectedAccounts.size} аккаунтов
          </p>

          {loading && groupsBySocial.length === 0 ? (
            <p>Загрузка групп...</p>
          ) : (
            <div className="social-groups">
              {groupsBySocial.map((socialGroup) => {
                const isExpanded = expandedSocials.has(socialGroup.social);
                const allSelected = socialGroup.groups.every(group => {
                  const accountKey = JSON.stringify({
                    id: group.id,
                    social: group.social,
                    type: group.type
                  });
                  return selectedAccounts.has(accountKey);
                });

                return (
                  <div key={socialGroup.social} className="social-group">
                    <div className="social-header">
                      <button
                        onClick={() => toggleSocial(socialGroup.social)}
                        className="social-toggle"
                      >
                        {isExpanded ? '▼' : '▶'} {getSocialName(socialGroup.social)} ({socialGroup.count})
                      </button>
                      <label className="select-all-checkbox">
                        <input
                          type="checkbox"
                          checked={allSelected}
                          onChange={() => toggleAllInSocial(socialGroup.social)}
                        />
                        Выбрать все
                      </label>
                    </div>

                    {isExpanded && (
                      <div className="accounts-list">
                        {socialGroup.groups.map((group) => {
                          const account = {
                            id: group.id,
                            social: group.social,
                            type: group.type
                          };
                          const accountKey = JSON.stringify(account);
                          const isSelected = selectedAccounts.has(accountKey);

                          return (
                            <div key={group.id} className="account-item">
                              <label className="account-checkbox">
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={() => toggleAccount(account)}
                                />
                                <span className="account-name">{group.name || `${getSocialName(group.social)} ${group.id}`}</span>
                                <span className="account-type">({group.type})</span>
                              </label>
                            </div>
                          );
                        })}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </div>

        <div className="section">
          <button
            onClick={handlePublish}
            disabled={loading || selectedAccounts.size === 0 || !videoFile || !publishDate || !publishTime}
            className="publish-button"
          >
            {loading ? 'Публикация...' : 'Опубликовать'}
          </button>
        </div>
      </div>
    </div>
  );
}

export default App;

