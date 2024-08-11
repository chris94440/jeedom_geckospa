<?php
/* This file is part of Jeedom.
*
* Jeedom is free software: you can redistribute it and/or modify
* it under the terms of the GNU General Public License as published by
* the Free Software Foundation, either version 3 of the License, or
* (at your option) any later version.
*
* Jeedom is distributed in the hope that it will be useful,
* but WITHOUT ANY WARRANTY; without even the implied warranty of
* MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
* GNU General Public License for more details.
*
* You should have received a copy of the GNU General Public License
* along with Jeedom. If not, see <http://www.gnu.org/licenses/>.
*/

/* * ***************************Includes********************************* */
require_once __DIR__  . '/../../../../core/php/core.inc.php';

class geckospa extends eqLogic {

    const PYTHON_PATH = __DIR__ . '/../../resources/python_venv/bin/python3';

    public static function getcmdName($name) {
      	return str_replace(array('lights','pumps','waterCare','sensorBinary','sensor','waterHeater'),array('Lumière','Pompe','Traitement de l\'eau','Capteur binaire','Capteur','Chauffage'),$name);
    }

    public static function getCmdState($state) {
      	return str_replace(array('Away From Home','Energy Saving','Standard','Super Energy Saving','Weekender','state','ON','OFF','LO','HI','stateString'),array('En dehors de la maison', 'Economie d\énergie', 'Standard','Super economie d\énergie','Week-end', 'Etat','On','Off','Doucement','Fort','Etat détail'),$state);

    }

/* Gestion des dépendances */
public static function dependancy_install() {
  log::remove(__CLASS__ . '_update');
  return array('script' => __DIR__ . '/../../resources/install_apt.sh', 'log' => log::getPathToLog(__CLASS__ . '_update'));
}

public static function dependancy_info() {
  $return = array();
  $return['log'] = log::getPathToLog(__CLASS__ . '_update');
  $return['progress_file'] = jeedom::getTmpFolder(__CLASS__) . '/dependance';
  $return['state'] = 'ok';
  if (file_exists(jeedom::getTmpFolder(__CLASS__) . '/dependance')) {
    $return['state'] = 'in_progress';
  } elseif (!file_exists(self::PYTHON_PATH)) {
    $return['state'] = 'nok';
  } elseif (exec(self::PYTHON_PATH . ' -m pip list | grep -Ewc "urllib3|aiohttp|pyserial|geckolib|requests"') < 5) {
    $return['state'] = 'nok';
  }
  return $return;
}


/* Gestion du démon */
  public static function deamon_info() {
    $return = array();
    $return['log'] = __CLASS__;
    $return['state'] = 'nok';
    $pid_file = jeedom::getTmpFolder(__CLASS__) . '/geckospad.pid';
    if (file_exists($pid_file)) {
        if (@posix_getsid(trim(file_get_contents($pid_file)))) {
            $return['state'] = 'ok';
        } else {
            shell_exec(system::getCmdSudo() . 'rm -rf ' . $pid_file . ' 2>&1 > /dev/null');
        }
    }
    $return['launchable'] = 'ok';
    //$user = config::byKey('user', __CLASS__); // exemple si votre démon à besoin de la config user,
    //$pswd = config::byKey('password', __CLASS__); // password,
    // $clientId = config::byKey('clientId', __CLASS__); // et clientId
    $portDaemon=config::byKey('daemonPort', __CLASS__);
    /*
    if ($user == '') {
        $return['launchable'] = 'nok';
        $return['launchable_message'] = __('Le nom d\'utilisateur n\'est pas configuré', __FILE__);
    } elseif ($pswd == '') {
        $return['launchable'] = 'nok';
        $return['launchable_message'] = __('Le mot de passe n\'est pas configuré', __FILE__);
     } elseif ($clientId == '') {
         $return['launchable'] = 'nok';
         $return['launchable_message'] = __('La clé d\'application n\'est pas configurée', __FILE__);
    }
    */
    return $return;
}

public static function deamon_start() {
  self::deamon_stop();
  $deamon_info = self::deamon_info();
  if ($deamon_info['launchable'] != 'ok') {
      throw new Exception(__('Veuillez vérifier la configuration', __FILE__));
  }

  /*$webhook_ip = "";
    $callbackip_cfg = config::byKey('ipwebhook', __CLASS__, '0');
    if ($callbackip_cfg == 1) {
      // Internal
      $webhook_ip = network::getNetworkAccess('internal', 'ip');
    } elseif ($callbackip_cfg == 2) {
      // External
      $webhook_ip = network::getNetworkAccess('external', 'ip');
    } elseif ($callbackip_cfg == 3) {
      // Personnalised
      $webhook_ip = config::byKey('webhookdefinedip', __CLASS__, '');
    }*/

    $path = realpath(dirname(__FILE__) . '/../../resources');
    $cmd = self::PYTHON_PATH . " {$path}/geckospad/geckospad.py";
    $cmd .= ' --loglevel ' . log::convertLogLevel(log::getLogLevel(__CLASS__));
    $cmd .= ' --socketport ' . config::byKey('socketport', __CLASS__, '55009');
    $cmd .= ' --callback ' . network::getNetworkAccess('internal', 'proto:127.0.0.1:port:comp') . '/plugins/geckospa/core/php/jeeGeckospa.php';
    $cmd .= ' --apikey ' . jeedom::getApiKey(__CLASS__);
    $cmd .= ' --pid ' . jeedom::getTmpFolder(__CLASS__) . '/geckospad.pid';
    $cmd .= ' --clientId "' . trim(str_replace('"', '\"', self::guidv4())) . '"';
    
    log::add(__CLASS__, 'info', 'Lancement démon');
    $result = exec($cmd . ' >> ' . log::getPathToLog('geckospa_daemon') . ' 2>&1 &');
    $i = 0;
    while ($i < 20) {
      $deamon_info = self::deamon_info();
      if ($deamon_info['state'] == 'ok') {
        break;
      }
      sleep(1);
      $i++;
    }
    if ($i >= 30) {
      log::add(__CLASS__, 'error', __('Impossible de lancer le démon, vérifiez le log', __FILE__), 'unableStartDeamon');
      return false;
    }
    message::removeAll(__CLASS__, 'unableStartDeamon');
    return true;
}

private static function guidv4() {
    $data = random_bytes(16);
    assert(strlen($data) == 16);

    $data[6] = chr(ord($data[6]) & 0x0f | 0x40);
    $data[8] = chr(ord($data[8]) & 0x3f | 0x80);
    
    return vsprintf('%s%s-%s-%s-%s-%s%s%s', str_split(bin2hex($data), 4));
}

public static function deamon_stop() {
  $pid_file = jeedom::getTmpFolder(__CLASS__) . '/geckospad.pid'; // ne pas modifier
  if (file_exists($pid_file)) {
      $pid = intval(trim(file_get_contents($pid_file)));
      system::kill($pid);
  }
  system::kill('geckospad.py'); // nom du démon à modifier
  sleep(1);
}

public static function synchronize() {
    self::sendToDaemon(['action' => 'synchronize']);
    //sleep(5);
}

protected static function getSocketPort() {
    return config::byKey('socketport', __CLASS__, 55009);
}

public function getImage() {
    return 'plugins/geckospa/data/img/gecko_equipment.png';
}

public static function sendToDaemon($params) {
  $deamon_info = self::deamon_info();
  if ($deamon_info['state'] != 'ok') {
      throw new Exception("Le démon n'est pas démarré");
  }
  $port = self::getSocketPort();
  $params['apikey'] = jeedom::getApiKey(__CLASS__);  
  $payLoad = json_encode($params);
  log::add(__CLASS__, 'debug', 'sendToDaemon -> ' . $payLoad);
  $socket = socket_create(AF_INET, SOCK_STREAM, SOL_TCP);
  socket_connect($socket, '127.0.0.1', $port);
  socket_write($socket, $payLoad, strlen($payLoad));
  socket_close($socket);
}


  /*     * *************************Attributs****************************** */

  public static function create_or_update_devices($spas) {
    log::add(__CLASS__, 'debug', 'create_or_update_devices -> '. $spas);
    $aSpas=json_decode($spas,true);
    $eqLogics=eqLogic::byType(__CLASS__);

    foreach ($aSpas['spas'] as $spa) {
        log::add(__CLASS__, 'debug', '  - spa : ' . json_encode($spa));

        $found = false;
        foreach ($eqLogics as $eqLogic) {
            if ($spa['id'] == $eqLogic->getLogicalId()) {
                $eqLogic_found = $eqLogic;
                $found = true;
                break;
            }
        }

        if (!$found) {
            log::add(__CLASS__, 'debug', '      -> spa not exist -> create it');
             $eqLogic = new eqLogic();
             $eqLogic->setEqType_name(__CLASS__);
             $eqLogic->setIsEnable(1);
             $eqLogic->setIsVisible(1);
             $eqLogic->setName($spa['name']);
             $eqLogic->setConfiguration('id', $spa['id']);
             $eqLogic->setLogicalId($spa['id']);
             $eqLogic->save();

             $eqLogic = self::byId($eqLogic->getId());

        } else {
            $eqLogic=$eqLogic_found;
            
        }
      

        foreach($spa['cmds'] as $cmd) {
            log::add(__CLASS__, 'debug', '          * Cmd name : ' . $cmd['name'] . ' -> ' . $cmd['state']);
          	if (array_key_exists('state',$cmd) && array_key_exists('name',$cmd)) {

                $cmdName=$cmd['name'].'_state';
                if (array_key_exists('label',$cmd)) {
                    $cmdName=$cmd['label'];
                } 
               	
              	$geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
              	if ($cmd['name'] == 'waterHeater') {
                	log::add(__CLASS__, 'debug', '                  -> Create cmds linked to waterheater function');
                } else {
                  	//create cmd info state
                    if (!(is_object($geckoSpaCmd))) {
                        log::add(__CLASS__, 'debug', '                  -> Create cmd : ' . $cmdName);
                        $geckoSpaCmd = new geckospaCmd();                        
                        $geckoSpaCmd->setName(self::buildCmdName($cmdName));                        
                        $geckoSpaCmd->setLogicalId($cmdName);                        
                        $geckoSpaCmd->setEqLogic_id($eqLogic->getId());                        
                        $geckoSpaCmd->setIsVisible(1); 
                        $geckoSpaCmd->setType('info');
                        
                        if(is_bool($cmd['state'])) {                          
                          $geckoSpaCmd->setSubType('binary');
                        } else {                            
                          $geckoSpaCmd->setSubType('string');
                        }  

                        $geckoSpaCmd->save();
                    } else {
                        log::add(__CLASS__, 'debug', '                  -> cmd exist : ' . $geckoSpaCmd->getName() . '|' . $geckoSpaCmd->getType(). '|'.$geckoSpaCmd->getSubType());
                    }


                    //set or update value
                    if ($cmd['state'] != '') {
                        if(is_bool($cmd['state'])) {
                            $geckoSpaCmd->event((boolean) $cmd['state']);
                        } else {
                            $geckoSpaCmd->event($cmd['state']);
                        }
                    } else {
                      if ($geckoSpaCmd->getSubType() == 'binary') {
                      		$geckoSpaCmd->event((boolean) false);
                      }
                    }
                  
                    if (array_key_exists('stateString',$cmd)) {
                        $cmdName=$cmd['name'].'_stateString';
                        $geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
                        if (!(is_object($geckoSpaCmd))) {
                          	$geckoSpaCmd = new geckospaCmd();
                            $geckoSpaCmd->setName(self::buildCmdName($cmdName));
                            $geckoSpaCmd->setLogicalId($cmdName);
                            $geckoSpaCmd->setEqLogic_id($eqLogic->getId());
                            $geckoSpaCmd->setIsVisible(1); 
                            $geckoSpaCmd->setType('info');
                            $geckoSpaCmd->setSubType('string');
                            $geckoSpaCmd->save();
                        }
                    }

                    if ($cmd['stateList'] != '') {
                        if ($cmd['state'] != '') {
                            $i=0;
                            foreach($cmd['stateList'] as $stateString) {
                                if ( $cmd['state'] == $i) {
                                    $geckoSpaCmd->event($stateString);
                                    break;
                                }
                                $i++;
                            }
                        }
                    }
                }  
              
            }

            if (array_key_exists('mode',$cmd) && array_key_exists('name',$cmd)) {
                $cmdName=$cmd['name'].'_mode';
              	$geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
                if (!(is_object($geckoSpaCmd))) {
                    log::add(__CLASS__, 'debug', '                  -> Create cmd : ' . $cmdName);
                    $geckoSpaCmd = new geckospaCmd();
                    $geckoSpaCmd->setName(self::buildCmdName($cmdName));
                    $geckoSpaCmd->setLogicalId($cmdName);
                    $geckoSpaCmd->setEqLogic_id($eqLogic->getId());
                    $geckoSpaCmd->setIsVisible(1); 
                    $geckoSpaCmd->setType('info');
                    $geckoSpaCmd->setSubType('string');
                    $geckoSpaCmd->save();
                }

                //set or update value
                if ($cmd['mode'] != '') {
                    $geckoSpaCmd->event($cmd['mode']);
                }
            }
          
          
          	if ($cmd['name'] == 'waterHeater') {
              	log::add(__CLASS__, 'debug', '                  -> Create cmds linked to waterheater function');
                self::createCmdsWaterHeater($eqLogic,$cmd);
            }
          
          	//create cmd action 
          	if (array_key_exists('stateList',$cmd) && array_key_exists('name',$cmd)) {
                $i=0;
              	foreach($cmd['stateList'] as $state) {
                    $cmdName=$cmd['name'].'_'.$state;
                    $geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
                    if (!(is_object($geckoSpaCmd))) {
                        $geckoSpaCmd = new geckospaCmd();
                        $geckoSpaCmd->setType('action');
                        $geckoSpaCmd->setIsVisible(1);
                        $geckoSpaCmd->setSubType('other');
                        $geckoSpaCmd->setName(self::buildCmdName($cmdName));
                        $geckoSpaCmd->setLogicalId($cmdName);
                        $geckoSpaCmd->setEqLogic_id($eqLogic->getId());
                        
                    }
                    $geckoSpaCmd->setConfiguration("indState",$i);
                    $geckoSpaCmd->save();
                    $i++;
                }
            }
          
        }
      
     }

  }

  private static function createCmdsWaterHeater($eqLogic,$cmd) {
    log::add(__CLASS__, 'debug', '                  -> START Create cmds linked to waterheater function');
    if (array_key_exists('current_temp',$cmd) ) {
        $cmdName='Température eau';
        $geckoSpaCmd = $eqLogic->getCmd(null, 'current_temp');
        if (!(is_object($geckoSpaCmd))) {
            $geckoSpaCmd = new geckospaCmd();
            $geckoSpaCmd->setName($cmdName);
            $geckoSpaCmd->setLogicalId('current_temp');
            $geckoSpaCmd->setEqLogic_id($eqLogic->getId());
            $geckoSpaCmd->setIsVisible(1); 
            $geckoSpaCmd->setType('info');
            $geckoSpaCmd->setSubType('numeric');
            
            if (array_key_exists('min_temp',$cmd) ) {
                $geckoSpaCmd->setConfiguration('minValue',0);
            }

            if (array_key_exists('max_temp',$cmd) ) {
                $geckoSpaCmd->setConfiguration('max_temp',50);
            }
            
            $geckoSpaCmd->save();
        }
        $geckoSpaCmd->event($cmd['current_temp']);
        log::add(__CLASS__, 'debug', '                  -> Create cmds current_temp');
    }

    $geckoSpaCmd->event($cmd['current_temp']);

    if (array_key_exists('current_operation',$cmd) ) {
      $cmdName='Opération';
      $geckoSpaCmd = $eqLogic->getCmd(null, 'current_operation');
      if (!(is_object($geckoSpaCmd))) {
          $geckoSpaCmd = new geckospaCmd();
          $geckoSpaCmd->setName($cmdName);
          $geckoSpaCmd->setLogicalId('current_operation');
          $geckoSpaCmd->setEqLogic_id($eqLogic->getId());
          $geckoSpaCmd->setIsVisible(1); 
          $geckoSpaCmd->setType('info');
          $geckoSpaCmd->setSubType('string');
          
          $geckoSpaCmd->save();
      }
      $geckoSpaCmd->event($cmd['current_operation']);

    }

  $geckoSpaCmd->event($cmd['current_operation']);
  log::add(__CLASS__, 'debug', '                  -> Create cmds current_operation');


    if (array_key_exists('target_temperature',$cmd) ) {
        $cmdName='Chauffer eau';
        $geckoSpaCmd = $eqLogic->getCmd(null, 'target_temperature_slider');
        if (!(is_object($geckoSpaCmd))) {
            $geckoSpaCmdAskTemp = new geckospaCmd();
            $geckoSpaCmdAskTemp->setName('Température demandée');
            $geckoSpaCmdAskTemp->setLogicalId('target_temperature');
            $geckoSpaCmdAskTemp->setEqLogic_id($eqLogic->getId());
            $geckoSpaCmdAskTemp->setIsVisible(1); 
            $geckoSpaCmdAskTemp->setType('info');
            $geckoSpaCmdAskTemp->setSubType('numeric');
            
            if (array_key_exists('min_temp',$cmd) ) {
                $geckoSpaCmdAskTemp->setConfiguration('minValue',$cmd['min_temp']);
            }

            if (array_key_exists('max_temp',$cmd) ) {
                $geckoSpaCmdAskTemp->setConfiguration('max_temp',$cmd['max_temp']);
            }
            
            $geckoSpaCmdAskTemp->save();
            log::add(__CLASS__, 'debug', '                  -> Create info target_temperature');

            $geckoSpaCmd = new geckospaCmd();
            $geckoSpaCmd->setName($cmdName);
            $geckoSpaCmd->setLogicalId('target_temperature_slider');
            $geckoSpaCmd->setEqLogic_id($eqLogic->getId());
            $geckoSpaCmd->setIsVisible(1); 
            $geckoSpaCmd->setType('action');
            $geckoSpaCmd->setSubType('slider');
            $geckoSpaCmd->setValue($geckoSpaCmdAskTemp->getId());
            
            if (array_key_exists('min_temp',$cmd) ) {
                $geckoSpaCmd->setConfiguration('minValue',$cmd['min_temp']);
            }

            if (array_key_exists('max_temp',$cmd) ) {
                $geckoSpaCmd->setConfiguration('maxValue',$cmd['max_temp']);
            }
            
            $geckoSpaCmd->save();
            log::add(__CLASS__, 'debug', '                  -> Create cmds target_temperature_slider');
        }

        $geckoSpaCmd = $eqLogic->getCmd(null, 'target_temperature');
        if (is_object($geckoSpaCmd)) {
            $geckoSpaCmd->event($cmd['target_temperature']);
            log::add(__CLASS__, 'debug', '                  -> Create cmds target_temperature');
        }


    }
    log::add(__CLASS__, 'debug', '                  -> END Create cmds linked to waterheater function');
  }

  private static function buildCmdName($cmdName) {
    $aCmdName=explode('_',$cmdName);
    if (sizeof($aCmdName) > 2) {
        return self::getcmdName($aCmdName[0]) . ' ' . $aCmdName[1] . ' ' . self::getCmdState($aCmdName[2]);
    } elseif ( sizeof($aCmdName) == 2){
        return self::getcmdName($aCmdName[0]) . ' ' . self::getCmdState($aCmdName[1]);
    } else {
        return $cmdName;
    }
  }

  public static function updateItems($updateItems) {
    log::add(__CLASS__, 'debug', 'updateItems -> ' . $updateItems);
    $aSpas=json_decode($updateItems,true);
    $eqLogics=eqLogic::byType(__CLASS__);
    $found = false;

    if (array_key_exists('id',$aSpas)) {
		log::add(__CLASS__, 'debug', '	- spa id : ' . $aSpas['id']);
        foreach ($eqLogics as $eqLogic) {
            if ($aSpas['id'] == $eqLogic->getLogicalId()) {
                $eqLogic_found = $eqLogic;
                $found = true;
                break;
            }
    }

    if ($found) {
        if (array_key_exists('cmds',$aSpas))
            foreach($aSpas['cmds'] as $cmd) {
                if (array_key_exists('state',$cmd)) {
                  	log::add(__CLASS__, 'debug', '		- cmd : ' . $cmd['name'] . '|'.$cmd['label'] . '|'.$cmd['state'] . '('. strlen($cmd['state']).')');
                      log::add(__CLASS__, 'debug', '		- json cmd : ' . json_encode($cmd));
                    $cmdName=$cmd['name'].'_state';
                    if (array_key_exists('label',$cmd)) {
                        $cmdName=$cmd['label'];
                    } 
               	
                  	log::add(__CLASS__, 'debug', '	 - search for cmd : ' . $cmdName);
              	    $geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
                    if (is_object($geckoSpaCmd)) {
                      	log::add(__CLASS__, 'debug', '			- update ' . $cmdName . ' by ' . $cmd['state']);
                      	if ($cmd['state'] != '') {
                          	
                            if(is_bool($cmd['state'])) {
                                log::add(__CLASS__, 'debug', '			    -> update type boolean');
                                $geckoSpaCmd->event((boolean) $cmd['state']);
                            } else {
                                log::add(__CLASS__, 'debug', '			    -> update type string');
                                $geckoSpaCmd->event($cmd['state']);
                            }
                        } else {
                          if ($geckoSpaCmd->getSubType() == 'binary') {
                                $geckoSpaCmd->event((boolean) false);
                          }
                        }
                      
                      	
                    }
                }

                if (array_key_exists('mode',$cmd)) {
                    $cmdName=$cmd['name'].'_mode';
                    log::add(__CLASS__, 'debug', '	 - search for cmd : ' . $cmdName);
                    $geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
                    if (is_object($geckoSpaCmd)) {
                            log::add(__CLASS__, 'debug', '			- update ' . $cmdName . ' by ' . $cmd['mode']);
                            if ($cmd['mode'] != '') {
                                $geckoSpaCmd->event($cmd['mode']);
                            }                                                    
                    }
                }

                if (array_key_exists('stateString',$cmd)) {                    
                    $cmdName=$cmd['name'].'_stateString';
                    log::add(__CLASS__, 'debug', '			- update ' . $cmdName . ' with state ' . $cmd['state'] . ' and stateString -> '. $cmd['stateString']);
                    $geckoSpaCmd = $eqLogic->getCmd(null, $cmdName);
                    if (is_object($geckoSpaCmd)) {
                        if ($cmd['stateList'] != '') {
                            if ($cmd['state'] != '') {
                                $i=0 ;
                                foreach($cmd['stateList'] as $stateString) {
                                    if ( $cmd['state'] == $i) {
                                        $geckoSpaCmd->event($stateString);
                                        break;
                                    }
                                    $i++;
                                }
                            }
                        }
                    }
                }

                if ($cmd['name'] == 'waterHeater') {
                    $geckoSpaCmd = $eqLogic->getCmd(null, 'current_temp');
                    if (is_object($geckoSpaCmd)) {
                      	log::add(__CLASS__, 'debug', '			- update current_temp by ' . $cmd['current_temp']);
                        $geckoSpaCmd->event($cmd['current_temp']);
                    }

                    $geckoSpaCmd = $eqLogic->getCmd(null, 'target_temperature');
                    if (is_object($geckoSpaCmd)) {
                      	log::add(__CLASS__, 'debug', '			- update target_temperature by ' . $cmd['target_temperature']);
                        $geckoSpaCmd->event($cmd['target_temperature']);
                    }

                    $geckoSpaCmd = $eqLogic->getCmd(null, 'current_operation');
                    if (is_object($geckoSpaCmd)) {
                      	log::add(__CLASS__, 'debug', '			- update current_operation by ' . $cmd['current_operation']);
                        $geckoSpaCmd->event($cmd['current_operation']);
                    }                    
                }
            }
        }

    }
    //self::create_or_update_devices($updateItems);
    
  }

  /*
  * Permet de définir les possibilités de personnalisation du widget (en cas d'utilisation de la fonction 'toHtml' par exemple)
  * Tableau multidimensionnel - exemple: array('custom' => true, 'custom::layout' => false)
  public static $_widgetPossibility = array();
  */

  /*
  * Permet de crypter/décrypter automatiquement des champs de configuration du plugin
  * Exemple : "param1" & "param2" seront cryptés mais pas "param3"
  public static $_encryptConfigKey = array('param1', 'param2');
  */

  /*     * ***********************Methode static*************************** */

  /*
  * Fonction exécutée automatiquement toutes les minutes par Jeedom
  public static function cron() {}
  */

 /*
  * Fonction exécutée automatiquement toutes les 5 minutes par Jeedom
  */

  public static function cron5() {
    $eqLogics=eqLogic::byType(__CLASS__);
    foreach ($eqLogics as $eqLogic) {
        self::sendToDaemon(['action' => 'synchronizeBySpaId', 'spaId' => $eqLogic->getLogicalId()]);
    }
  }



  /*
  * Fonction exécutée automatiquement toutes les 10 minutes par Jeedom
  */
  /*
  public static function cron10() {
    self::synchronize();
  }
  */
  

  /*
  * Fonction exécutée automatiquement toutes les 15 minutes par Jeedom
  public static function cron15() {}
  */

  /*
  * Fonction exécutée automatiquement toutes les 30 minutes par Jeedom
  public static function cron30() {}
  */

  /*
  * Fonction exécutée automatiquement toutes les heures par Jeedom
  public static function cronHourly() {}
  */

  /*
  * Fonction exécutée automatiquement tous les jours par Jeedom
  public static function cronDaily() {}
  */
  
  /*
  * Permet de déclencher une action avant modification d'une variable de configuration du plugin
  * Exemple avec la variable "param3"
  public static function preConfig_param3( $value ) {
    // do some checks or modify on $value
    return $value;
  }
  */

  /*
  * Permet de déclencher une action après modification d'une variable de configuration du plugin
  * Exemple avec la variable "param3"
  public static function postConfig_param3($value) {
    // no return value
  }
  */

  /*
   * Permet d'indiquer des éléments supplémentaires à remonter dans les informations de configuration
   * lors de la création semi-automatique d'un post sur le forum community
   public static function getConfigForCommunity() {
      return "les infos essentiel de mon plugin";
   }
   */

  /*     * *********************Méthodes d'instance************************* */

  // Fonction exécutée automatiquement avant la création de l'équipement
  public function preInsert() {
  }

  // Fonction exécutée automatiquement après la création de l'équipement
  public function postInsert() {
  }

  // Fonction exécutée automatiquement avant la mise à jour de l'équipement
  public function preUpdate() {
  }

  // Fonction exécutée automatiquement après la mise à jour de l'équipement
  public function postUpdate() {
  }

  // Fonction exécutée automatiquement avant la sauvegarde (création ou mise à jour) de l'équipement
  public function preSave() {
  }

  // Fonction exécutée automatiquement après la sauvegarde (création ou mise à jour) de l'équipement
  public function postSave() {
  }

  // Fonction exécutée automatiquement avant la suppression de l'équipement
  public function preRemove() {
  }

  // Fonction exécutée automatiquement après la suppression de l'équipement
  public function postRemove() {
  }

  /*
  * Permet de crypter/décrypter automatiquement des champs de configuration des équipements
  * Exemple avec le champ "Mot de passe" (password)
  public function decrypt() {
    $this->setConfiguration('password', utils::decrypt($this->getConfiguration('password')));
  }
  public function encrypt() {
    $this->setConfiguration('password', utils::encrypt($this->getConfiguration('password')));
  }
  */

  /*
  * Permet de modifier l'affichage du widget (également utilisable par les commandes)
  public function toHtml($_version = 'dashboard') {}
  */

  /*     * **********************Getteur Setteur*************************** */
}

class geckospaCmd extends cmd {
  /*     * *************************Attributs****************************** */

  /*
  public static $_widgetPossibility = array();
  */

  /*     * ***********************Methode static*************************** */


  /*     * *********************Methode d'instance************************* */

  /*
  * Permet d'empêcher la suppression des commandes même si elles ne sont pas dans la nouvelle configuration de l'équipement envoyé en JS
  public function dontRemoveCmd() {
    return true;
  }
  */

  // Exécution d'une commande
  public function execute($_options = array()) {
    $eqlogic = $this->getEqLogic();
    $logicalId=$this->getLogicalId();

    $type=$this->type;
    $subType=$this->subType;
    log::add('geckospa', 'debug','   - Execute ' . $logicalId . ' with options value : ' .json_encode($_options));
    
    if ($this->type == 'action') {
      $aExecCmd=explode('_',$logicalId);
      
      
      $valueToSend = '';
      switch (true){
         case stristr($logicalId,'target_temperature_slider'):
            $geckoSpaCmd = $eqlogic->getCmd(null, 'target_temperature');
            $value=$_options['slider'];
            $valueToSend = ['spaIdentifier' => $eqlogic->getLogicalId(), 'action' => 'execCmd', 'cmd' => 'target_temperature', 'ind' => 0, 'value'=> $value];
            break;
         case stristr($logicalId,'waterCare'):
           	//$valueToSend = ['spaIdentifier' => $eqlogic->getLogicalId(), 'action'=>'execCmd','cmd' => 'waterCare', 'ind' => 0, 'value'=> $this->getConfiguration('indState')];
          	$valueToSend = ['spaIdentifier' => $eqlogic->getLogicalId(), 'action'=>'execCmd','cmd' => 'waterCare', 'ind' => 0, 'value'=> (explode('_',$logicalId))[1]];
            break;
         default:
            if (sizeof($aExecCmd) > 2 ) {
              //log::add('geckospa', 'debug','   	-> ' .json_encode(['spaIdentifier' => $eqlogic->getLogicalId(), 'action'=>'execCmd','cmd' => $aExecCmd[0], 'ind' => $aExecCmd[1], 'value'=>$aExecCmd[2]]));
              $valueToSend = ['spaIdentifier' => $eqlogic->getLogicalId(), 'action'=>'execCmd','cmd' => $aExecCmd[0], 'ind' => $aExecCmd[1], 'value'=>$aExecCmd[2]];
            }  elseif (sizeof($aExecCmd) == 2 ) {
              //log::add('geckospa', 'debug','   	-> ' .json_encode(['spaIdentifier' => $eqlogic->getLogicalId(), 'action'=>'execCmd','cmd' => $aExecCmd[0], 'ind' => 0, 'value'=>$aExecCmd[2]]));
              $valueToSend = ['spaIdentifier' => $eqlogic->getLogicalId(), 'action'=>'execCmd','cmd' => $aExecCmd[0], 'ind' => 0, 'value'=>$aExecCmd[2]];

            }
            break;
      }
      
      if ($valueToSend != '') {
        	$eqlogic->sendToDaemon($valueToSend);
      }
    }
    
    if ($this->type == 'info') {
        return;
    }
  }

  /*     * **********************Getteur Setteur*************************** */
}