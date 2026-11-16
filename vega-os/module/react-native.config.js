module.exports = {
  dependency: {
    platforms: {
      kepler: {
        autolink: {
          'com.anshuva.tvfilelink.files': {
            libraryName: 'libFileLink.so',
            provider: 'application',
            linkDynamic: true,
            turbomodules: ['FileLink'],
          },
        },
      },
    },
  },
};
