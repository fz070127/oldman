/**
 * 图片人体状态检测 API
 */
import request from './request'

export interface DetectionGeometry {
  torsoAngle: number | null
  aspectRatio: number
  bodyHeight: number
  lyingPose: boolean
}

export interface DetectionResult {
  status: 'NORMAL' | 'SUSPECT' | 'FALL' | 'NO_PERSON'
  label: string
  score: number
  modelScore: number | null
  geometry: DetectionGeometry | null
  keypoints: [number, number, number][]
  box: number[]
  detectionScore?: number
  imageSize: [number, number]
  basis: string
}

/** 上传图片并判断人体状态（真实推理，非前端动画） */
export function detectImage(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<DetectionResult>({
    url: '/detection/image',
    method: 'post',
    data: form,
    silentError: true,
  })
}
