export type IqGeneratorSettings = {
  iq_bits: number
  iq_sample_rate_hz: number
}

export type GpsTransmitterSettings = {
  center_freq_hz: number
  sample_rate_hz: number
  txvga_gain: number
  amp_enabled: boolean
}

export type ControllerSettings = {
  port: string
}

export type AppSettings = {
  iq_generator: IqGeneratorSettings
  gps_transmitter: GpsTransmitterSettings
  controller: ControllerSettings
}
