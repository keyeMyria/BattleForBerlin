<template>
  <div id="map2" />
</template>
<script>
  import {buildLeafletMap} from '../helpers'
  import {AnimationLayer} from '../layers'
  import {mapState} from 'vuex'
  export default {
    name: 'animation-map',
    data () {
      return {
      }
    },
    computed: {
      ...mapState(['gerrymanderAnimation', 'districtHash'])
    },
    mounted () {
      this.map = buildLeafletMap(this.$el)
      this.renderer = new AnimationLayer(this.districtHash)
      this.renderer.runAnimation(this.gerrymanderAnimation)
      this.renderer.layers.addTo(this.map)
    }
  }
</script>

<style lang="sass" scoped>
#map2
  height: 600px
  width: 100%

</style>