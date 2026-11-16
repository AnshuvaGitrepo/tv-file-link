import type {KeplerTurboModule} from '@amazon-devices/keplerscript-turbomodule-api';
import {TurboModuleRegistry} from '@amazon-devices/keplerscript-turbomodule-api';

export interface FileLink extends KeplerTurboModule {
  operate: (root: string, action: string, path: string, name: string) => string;
}

export default TurboModuleRegistry.getEnforcing<FileLink>('FileLink');
