import L from 'leaflet'

import {maxProp, PARTY_COLORS, asyncChunks} from './helpers'

class BaseLayer {
  constructor () {
    this.config = {}
    this._cb = function () {}
    this.config.defaultStyle = this.config.defaultStyle || {
      style: styleDistrict
    }
    this.config.emphazisedStyle = this.config.emphazisedStyle || {
      style () { return {color: '#0078FF', weight: 1, opacity: 0.7} }
    }
    this.layers = L.layerGroup([])
  }

  selectDistrict (layer) {
    if (this._selectedLayer === layer) {
      this.reset()
      this._cb(undefined)
      return
    }
    this.reset()
    this._selectedLayer = layer
    layer.setStyle(this.config.emphazisedStyle.style(layer.feature))
    this._cb(layer.feature)
  }

  reset () {
    if (this._selectedLayer) {
      this._selectedLayer.setStyle(this.config.defaultStyle.style(this._selectedLayer.feature))
    }
    this._selectedLayer = undefined
  }

  onSelection (cb) {
    this._cb = cb
  }
}

export class DistrictLayer extends BaseLayer {
  updateDistricts (districts) {
    if (!districts) {
      return
    }
    const chunks = []
    for (let i = 0; i < districts.length; i += 50) {
      chunks.push(districts.slice(i, i + 50))
    }
    const $this = this
    this.layers.clearLayers()
    asyncChunks(districts, 400, 50).subscribe((district) => {
      const layer = L.geoJSON(district, this.config.defaultStyle)
      layer.on('click', function ({layer}) {
        $this.selectDistrict.bind($this)(layer)
      })
      this.layers.addLayer(layer)
    })
  }
}

export class CountyLayer extends BaseLayer {
  constructor () {
    super()
    this._countyLayers = {}
  }

  updateCounty (county) {
    if (!county) {
      return
    }
    const bwk = county.properties.bwk
    if (this._countyLayers[bwk]) {
      this._countyLayers[bwk].remove()
    }
    const $this = this
    const layer = L.geoJSON(county, this.config.defaultStyle)
    layer.on('click', function ({layer}) {
      $this.selectDistrict.bind($this)(layer)
    })
    this.layers.addLayer(layer)
    this._countyLayers[bwk] = layer
  }
}

export class AnimationLayer {
  constructor (districts) {
    this.layers = L.layerGroup([])
    this.districts = districts
    this._layerHash = {}
  }

  runAnimation (animation) {
    if (!animation) {
      return Promise.resolve()
    }
    return new Promise(function (resolve, reject) {
      asyncChunks(animation, 500, 1).subscribe(function (step) {
        if (step.action === 'search') {
          this.onSearch(step)
        }
        if (step.action === 'grow') {
          this.onGrow(step)
        }
      }.bind(this),
      console.error,
      () => resolve())
    }.bind(this))
  }

  onSearch ({candidates, winner}) {
    this.layers.clearLayers()
    for (let candidate of candidates) {
      let shape = this.districts[candidate]
      const fillColor = candidate === winner ? 'green' : 'yellow'
      let layer = L.geoJSON(shape, {color: 'black', fillColor, weight: 1, fillOpacity: 0.5})
      this._layerHash[candidate] = layer
      this.layers.addLayer(layer)
    }
  }

  onGrow ({targets}) {
    this.layers.clearLayers()
    for (let target of targets) {
      let layer = L.geoJSON(target, {style: styleDistrict})
      this.layers.addLayer(layer)
    }
  }
}

function styleDistrict ({geometry}) {
  const {properties} = geometry
  const winner = maxProp(properties.result)
  return {color: PARTY_COLORS[winner], weight: 1, opacity: 0.65}
}
