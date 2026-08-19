import api from './axios'

export const authApi = {
  login: (email, password) => api.post('/auth/login', { email, password }),
  register: (email, password, fullName, role = 'STUDENT') =>
    api.post('/auth/register', { email, password, full_name: fullName, role }),
}

export const labsApi = {
  getLabs: () => api.get('/labs'),
  getLab: (labId) => api.get(`/labs/${labId}`),
  getLabState: (labId) => api.get(`/labs/${labId}/state`),
}

export const pcsApi = {
  getLabPCs: (labId) => api.get(`/labs/${labId}/pcs`),
  toggleMaintenance: (pcId, isMaintenance) =>
    api.put(`/pcs/${pcId}/maintenance`, { is_maintenance: isMaintenance }),
}

export const softwareApi = {
  searchGlobal: (query) => api.get(`/software/search?q=${encodeURIComponent(query)}`),
  searchLab: (labId, query) =>
    api.get(`/labs/${labId}/software/search?q=${encodeURIComponent(query)}`),
}

export const timetableApi = {
  getLabTimetable: (labId) => api.get(`/labs/${labId}/timetable`),
  createTimetableEntry: (labId, data) => api.post(`/labs/${labId}/timetable`, data),
  deleteTimetableEntry: (timetableId) => api.delete(`/timetable/${timetableId}`),
  cancelSlot: (timetableId, cancelledForDate) =>
    api.post(`/timetable/${timetableId}/cancel`, {
      timetable_id: timetableId,
      cancelled_for_date: cancelledForDate,
    }),
  getLabCancellations: (labId) => api.get(`/labs/${labId}/cancellations`),
}

export const damageReportsApi = {
  submitReport: (pcId, issueDescription) =>
    api.post('/damage-reports', { pc_id: pcId, issue_description: issueDescription }),
  getReports: () => api.get('/damage-reports'),
  getPendingReports: () => api.get('/damage-reports/pending'),
  resolveReport: (reportId, status) =>
    api.put(`/damage-reports/${reportId}/resolve`, { status }),
}
