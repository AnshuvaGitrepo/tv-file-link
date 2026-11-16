import type { KeplerTurboModule } from '@amazon-devices/keplerscript-turbomodule-api';
export interface FileLink extends KeplerTurboModule {
    operate: (root: string, action: string, path: string, name: string) => string;
}
declare const _default: FileLink;
export default _default;
