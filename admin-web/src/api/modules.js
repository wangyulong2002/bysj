/**
 * 管理端业务接口（T2-1~T3-1，DRF ViewSet，/admin/api/**）
 * 统一返回 { code, message, data }；列表 data = { count, next, previous, results }
 */
import request from '../utils/request'

function crudApi(resource) {
  return {
    list(params) {
      return request.get(`/${resource}`, { params })
    },
    detail(id) {
      return request.get(`/${resource}/${id}`)
    },
    create(data) {
      return request.post(`/${resource}`, data)
    },
    update(id, data) {
      return request.put(`/${resource}/${id}`, data)
    },
    remove(id) {
      return request.delete(`/${resource}/${id}`)
    }
  }
}

export const departmentApi = crudApi('departments')
export const classApi = crudApi('classes')
export const courseApi = crudApi('courses')
export const termApi = crudApi('terms')
export const offeringApi = crudApi('offerings')
export const scheduleApi = crudApi('schedules')
export const studentApi = crudApi('students')
export const teacherApi = crudApi('teachers')

/** 公告：CRUD + 发布/下架（T3-1 状态机） */
export const announcementApi = {
  ...crudApi('announcements'),
  publish(id) {
    return request.post(`/announcements/${id}/publish`)
  },
  takeDown(id) {
    return request.post(`/announcements/${id}/take-down`)
  }
}
