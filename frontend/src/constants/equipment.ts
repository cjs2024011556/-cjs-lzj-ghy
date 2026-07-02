/**
 * 设备类型常量 - 前端单一来源
 * 演示场景：汽车制造产线（焊装/总装/冲压）
 */
export const EQUIPMENT_TYPES = [
  { value: '焊接机器人', label: '焊接机器人' },
  { value: 'AGV', label: 'AGV 移动机器人' },
  { value: '冲压机', label: '冲压机' },
  { value: '机器视觉', label: '机器视觉系统' },
] as const

export type EquipmentTypeValue = (typeof EQUIPMENT_TYPES)[number]['value']
